#!/usr/bin/env bash
# File-based prompt orchestration wrapper for claude CLI.
# Encapsulates the shared "External CLI prompt delivery" governance:
#   1. Active-availability probe — `command -v claude` before doing anything; fails closed.
#   2. Prompt body persisted to .scratch/claude-prompts/<topic>-<timestamp>.md
#   3. claude invoked with prompt redirected from that file (stdin), never via argv
#   4. stdout and stderr captured to sibling .out / .err files
#   5. Three output paths printed to stdout in order: prompt, out, err
#   6. Claude exit code propagated
#
# This wrapper is for the routine `claude` CLI (subscription auth or ambient API key).
# For the secret-backed API transport (`reserveResolver: claude-wrapper` path), use
# `invoke-claude-api.sh` instead — that wrapper layers SECRET.md env injection on top of
# the same file-based prompt discipline.
#
# Usage:
#   echo "<prompt body>" | bash .claude/agents/scripts/invoke-claude-prompt.sh <topic-slug> [-- claude-flags...]
#   bash .claude/agents/scripts/invoke-claude-prompt.sh <topic-slug> --prompt-file <path> [-- claude-flags...]
#
# Default claude flags (applied when no `--` block is given):
#   -p --output-format text --model opus --effort xhigh
# (the current claude CLI removed the top-level `--quiet` flag; `-p`/`--print` is the non-interactive mode)
#
# Environment overrides:
#   CLAUDE_BIN          Claude executable or absolute path (default: claude on PATH)
#   CLAUDE_PROMPTS_DIR  Output directory (default: .scratch/claude-prompts)
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  invoke-claude-prompt.sh <topic-slug> [--prompt-file <path>] [-- claude-flags...]

  Prompt body comes from stdin OR from --prompt-file <path>.

Output (printed to stdout in order):
  .scratch/claude-prompts/<topic-slug>-<timestamp>.md       # prompt body persisted
  .scratch/claude-prompts/<topic-slug>-<timestamp>.out      # claude stdout
  .scratch/claude-prompts/<topic-slug>-<timestamp>.err      # claude stderr

Environment:
  CLAUDE_BIN          Claude executable to invoke (default: claude on PATH)
  CLAUDE_PROMPTS_DIR  Output directory (default: .scratch/claude-prompts)
EOF
}

TOPIC=""
PROMPT_FILE=""
LEDGER_ITEM=""
LEDGER_ROLE="architecture-reviewer"
LEDGER_LANE=""
LEDGER_ARTIFACT=""
LEDGER_CLOSES=()
# Default flags (A12: every provider-backed run must carry an explicit model AND
# effort, never an ambient one) pin the shipped default profile `opus-xhigh` —
# the same fix already applied to the sibling invoke-codex-prompt.sh; without
# `--model`/`--effort` the run rides whatever ambient model the operator's
# Claude config selects, silently breaching the consultant xhigh floor.
# Callers needing a different profile pass the full per-profile flag set after `--`:
#   `opus-xhigh` (default / best-effort / consultant lane):
#     -- -p --output-format text --model opus --effort xhigh
#   `opus-max` (max-depth escalation for especially hard tasks):
#     -- -p --output-format text --model opus --effort max
#   `sonnet-high` (balanced/lighter tier):
#     -- -p --output-format text --model sonnet --effort high
# An explicit `--` block always overrides these defaults, including `--model`.
CLAUDE_FLAGS=("-p" "--output-format" "text" "--model" "opus" "--effort" "xhigh")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --prompt-file)
      PROMPT_FILE="$2"
      shift 2
      ;;
    --ledger)
      # Work-item dir: the dispatch PRODUCES its ledger events (decision
      # 2026-07-16-review-verdict-closure) — launch before the run, terminal after
      # it via the shared completion oracle below.
      LEDGER_ITEM="$2"
      shift 2
      ;;
    --ledger-role)
      LEDGER_ROLE="$2"
      shift 2
      ;;
    --ledger-lane)
      LEDGER_LANE="$2"
      shift 2
      ;;
    --ledger-artifact)
      LEDGER_ARTIFACT="$2"
      shift 2
      ;;
    --ledger-closes)
      # runId of an earlier REVISE this run re-verifies: a PASS terminal will carry
      # closesRunIds and discharge the obligation mechanically. Repeatable.
      LEDGER_CLOSES+=("$2")
      shift 2
      ;;
    --)
      shift
      CLAUDE_FLAGS=("$@")
      break
      ;;
    *)
      if [[ -z "$TOPIC" ]]; then
        TOPIC="$1"
      else
        echo "FAIL: unexpected positional argument '$1' (only one topic-slug allowed before --)" >&2
        usage >&2
        exit 1
      fi
      shift
      ;;
  esac
done

if [[ -z "$TOPIC" ]]; then
  echo "FAIL: <topic-slug> required as first positional argument" >&2
  usage >&2
  exit 1
fi

CLAUDE_CMD="${CLAUDE_BIN:-claude}"
if ! command -v "$CLAUDE_CMD" >/dev/null 2>&1; then
  echo "FAIL: claude binary '$CLAUDE_CMD' not found on PATH. Set CLAUDE_BIN if installed elsewhere." >&2
  exit 1
fi

OUTPUT_DIR="${CLAUDE_PROMPTS_DIR:-.scratch/claude-prompts}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SLUG="${TOPIC}-${TIMESTAMP}"

mkdir -p "$OUTPUT_DIR"
PROMPT_PATH="$OUTPUT_DIR/${SLUG}.md"
OUT_PATH="$OUTPUT_DIR/${SLUG}.out"
ERR_PATH="$OUTPUT_DIR/${SLUG}.err"

if [[ -n "$PROMPT_FILE" ]]; then
  if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "FAIL: --prompt-file '$PROMPT_FILE' does not exist" >&2
    exit 1
  fi
  cp "$PROMPT_FILE" "$PROMPT_PATH"
else
  if [[ -t 0 ]]; then
    echo "FAIL: no prompt provided (neither --prompt-file nor piped stdin)" >&2
    usage >&2
    exit 1
  fi
  cat > "$PROMPT_PATH"
fi

# --ledger: record the LAUNCH event before the run (fail closed on failure).
LAUNCH_RUN_ID=""
LEDGER_HELPER=""
if [[ -n "$LEDGER_ITEM" ]]; then
  for cand in "scripts/agent-run-ledger.py" "$(dirname "$0")/../../../scripts/agent-run-ledger.py"; do
    [[ -f "$cand" ]] && LEDGER_HELPER="$cand" && break
  done
  if [[ -z "$LEDGER_HELPER" ]]; then
    echo "FAIL: --ledger given but scripts/agent-run-ledger.py not found" >&2
    exit 1
  fi
  LAUNCH_RUN_ID="$(date -u +%Y%m%dT%H%M%S)Z-launch-${SLUG}"
  LEDGER_EFFORT=""
  for ((i=0; i<${#CLAUDE_FLAGS[@]}; i++)); do
    if [[ "${CLAUDE_FLAGS[$i]}" == "--effort" && -n "${CLAUDE_FLAGS[$((i+1))]:-}" ]]; then
      LEDGER_EFFORT="${CLAUDE_FLAGS[$((i+1))]}"
    fi
  done
  ledger_args=(--work-item "$LEDGER_ITEM" append --run-id "$LAUNCH_RUN_ID"     --role "$LEDGER_ROLE" --execution-role external-reviewer --provider claude     --status running --gate none --scope "external run: ${SLUG}"     --event-kind launch --prompt-file "$PROMPT_PATH"     --notes "wrapper-dispatched; terminal event follows the completion oracle")
  [[ -n "$LEDGER_LANE" ]] && ledger_args+=(--lane "$LEDGER_LANE")
  [[ -n "$LEDGER_ARTIFACT" ]] && ledger_args+=(--artifact "$LEDGER_ARTIFACT")
  [[ -n "$LEDGER_EFFORT" ]] && ledger_args+=(--effort "$LEDGER_EFFORT")
  if ! python "$LEDGER_HELPER" "${ledger_args[@]}" >/dev/null; then
    echo "FAIL: could not record launch event in $LEDGER_ITEM" >&2
    exit 1
  fi
fi

set +e
"$CLAUDE_CMD" "${CLAUDE_FLAGS[@]}" < "$PROMPT_PATH" 1> "$OUT_PATH" 2> "$ERR_PATH"
EXIT_CODE=$?
set -e

# Shared completion oracle: verdict accepted ONLY on exit 0 + clean .err + non-empty
# .out + FINAL non-blank line exactly `GATE: PASS|REVISE`; else blocked/none.
if [[ -n "$LEDGER_ITEM" ]]; then
  FINAL_LINE="$(grep -v '^[[:space:]]*$' "$OUT_PATH" 2>/dev/null | tail -1 | tr -d '')"
  ERR_MARKERS="$(grep -cE '^(ERROR|FATAL|API Error): ' "$ERR_PATH" 2>/dev/null || true)"
  TERM_STATUS="blocked"; TERM_GATE="none"; TERM_NOTE="oracle: "
  if [[ $EXIT_CODE -ne 0 ]]; then
    TERM_NOTE+="nonzero exit ($EXIT_CODE)"
  elif [[ ! -s "$OUT_PATH" ]]; then
    TERM_NOTE+="empty .out"
  elif [[ "${ERR_MARKERS:-0}" != "0" ]]; then
    TERM_NOTE+="err markers present ($ERR_MARKERS)"
  elif [[ "$FINAL_LINE" == "GATE: PASS" ]]; then
    TERM_STATUS="completed"; TERM_GATE="PASS"; TERM_NOTE+="final-line GATE: PASS"
  elif [[ "$FINAL_LINE" == "GATE: REVISE" ]]; then
    TERM_STATUS="revise"; TERM_GATE="REVISE"; TERM_NOTE+="final-line GATE: REVISE"
  else
    TERM_NOTE+="final line is not an anchored GATE verdict"
  fi
  term_args=(--work-item "$LEDGER_ITEM" append     --role "$LEDGER_ROLE" --execution-role external-reviewer --provider claude     --status "$TERM_STATUS" --gate "$TERM_GATE" --scope "external run: ${SLUG}"     --event-kind terminal --launch-run-id "$LAUNCH_RUN_ID"     --evidence "review:${OUT_PATH}" --notes "$TERM_NOTE")
  [[ -n "$LEDGER_LANE" ]] && term_args+=(--lane "$LEDGER_LANE")
  [[ -n "$LEDGER_ARTIFACT" ]] && term_args+=(--artifact "$LEDGER_ARTIFACT")
  [[ -n "$LEDGER_EFFORT" ]] && term_args+=(--effort "$LEDGER_EFFORT")
  if [[ "$TERM_GATE" == "PASS" && ${#LEDGER_CLOSES[@]} -gt 0 ]]; then
    for c in "${LEDGER_CLOSES[@]}"; do term_args+=(--closes "$c"); done
  fi
  python "$LEDGER_HELPER" "${term_args[@]}" >/dev/null     || echo "WARN: could not record terminal event in $LEDGER_ITEM" >&2
fi

echo "$PROMPT_PATH"
echo "$OUT_PATH"
echo "$ERR_PATH"

exit $EXIT_CODE

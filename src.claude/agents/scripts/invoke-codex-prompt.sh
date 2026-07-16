#!/usr/bin/env bash
# File-based prompt orchestration wrapper for codex CLI.
# Encapsulates the shared "External CLI prompt delivery" governance:
#   1. Active-availability probe — `command -v codex` before doing anything; fails closed.
#   2. Prompt body persisted to .scratch/codex-prompts/<topic>-<timestamp>.md
#   3. codex invoked with prompt redirected from that file (stdin), never via argv
#   4. stdout and stderr captured to sibling .out / .err files
#   5. Three output paths printed to stdout in order: prompt, out, err (so the caller can read them)
#   6. Codex exit code propagated
#
# Usage:
#   echo "<prompt body>" | bash .claude/agents/scripts/invoke-codex-prompt.sh <topic-slug> [-- codex-flags...]
#   bash .claude/agents/scripts/invoke-codex-prompt.sh <topic-slug> --prompt-file <path> [-- codex-flags...]
#
# Default codex flags (applied when no `--` block is given): --model gpt-5.6-sol -c model_reasoning_effort=xhigh
# (codex CLI 0.130.0+ runs via the `exec` subcommand, not the deprecated top-level --quiet/--full-auto)
#
# Environment overrides:
#   CODEX_BIN          Codex executable or absolute path (default: codex on PATH)
#   CODEX_PROMPTS_DIR  Output directory (default: .scratch/codex-prompts)
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  invoke-codex-prompt.sh <topic-slug> [--prompt-file <path>] [-- codex-flags...]

  Prompt body comes from stdin OR from --prompt-file <path>.

Output (printed to stdout in order):
  .scratch/codex-prompts/<topic-slug>-<timestamp>.md       # prompt body persisted
  .scratch/codex-prompts/<topic-slug>-<timestamp>.out      # codex stdout
  .scratch/codex-prompts/<topic-slug>-<timestamp>.err      # codex stderr

Environment:
  CODEX_BIN          Codex executable to invoke (default: codex on PATH)
  CODEX_PROMPTS_DIR  Output directory (default: .scratch/codex-prompts)
EOF
}

TOPIC=""
PROMPT_FILE=""
LEDGER_ITEM=""
LEDGER_ROLE="architecture-reviewer"
LEDGER_LANE=""
LEDGER_ARTIFACT=""
LEDGER_CLOSES=()
# Codex CLI 0.130.0+ uses `codex exec` (non-interactive subcommand) instead of the
# old top-level `--quiet --full-auto` flags. The wrapper invokes `codex exec` and
# supplies `--skip-git-repo-check` so prompts can be served from any directory.
#
# Default flags (A12: every provider-backed run must carry an explicit model AND
# effort, never an ambient one) pin the shipped default profile `gpt-5.6-sol-xhigh`.
# Callers needing a different profile pass the full per-profile flag set after `--`:
#   `gpt-5.6-sol-xhigh` (default / best-effort / consultant lane):
#     -- --model gpt-5.6-sol -c model_reasoning_effort=xhigh
#   `gpt-5.6-sol-max` (higher-complexity / hard lanes):
#     -- --model gpt-5.6-sol -c model_reasoning_effort=max
#   `gpt-5.6-terra` (balanced/cheap tier; a distinct model, not an effort suffix):
#     -- --model gpt-5.6-terra -c model_reasoning_effort=high
# An explicit `--` block always overrides these defaults, including `--model`.
CODEX_FLAGS=("--model" "gpt-5.6-sol" "-c" "model_reasoning_effort=xhigh")
SAW_DELIMITER=0
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
      # 2026-07-16-review-verdict-closure) — a launch event before the run and a
      # terminal event after it, parsed by the shared completion oracle below.
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
      SAW_DELIMITER=1
      shift
      CODEX_FLAGS=("$@")
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

CODEX_CMD="${CODEX_BIN:-codex}"
if ! command -v "$CODEX_CMD" >/dev/null 2>&1; then
  echo "FAIL: codex binary '$CODEX_CMD' not found on PATH. Set CODEX_BIN if installed elsewhere." >&2
  exit 1
fi

OUTPUT_DIR="${CODEX_PROMPTS_DIR:-.scratch/codex-prompts}"
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

# --ledger: record the LAUNCH event before the run (dispatch produces the record).
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
  if [[ "${CODEX_FLAGS[*]}" =~ model_reasoning_effort=\"?(low|medium|high|xhigh|max) ]]; then
    LEDGER_EFFORT="${BASH_REMATCH[1]}"
  fi
  ledger_args=(--work-item "$LEDGER_ITEM" append --run-id "$LAUNCH_RUN_ID" \
    --role "$LEDGER_ROLE" --execution-role external-reviewer --provider codex \
    --status running --gate none --scope "external run: ${SLUG}" \
    --event-kind launch --prompt-file "$PROMPT_PATH" \
    --notes "wrapper-dispatched; terminal event follows the completion oracle")
  [[ -n "$LEDGER_LANE" ]] && ledger_args+=(--lane "$LEDGER_LANE")
  [[ -n "$LEDGER_ARTIFACT" ]] && ledger_args+=(--artifact "$LEDGER_ARTIFACT")
  [[ -n "$LEDGER_EFFORT" ]] && ledger_args+=(--effort "$LEDGER_EFFORT")
  if ! python "$LEDGER_HELPER" "${ledger_args[@]}" >/dev/null; then
    echo "FAIL: could not record launch event in $LEDGER_ITEM" >&2
    exit 1
  fi
fi

set +e
"$CODEX_CMD" exec --skip-git-repo-check "${CODEX_FLAGS[@]}" < "$PROMPT_PATH" 1> "$OUT_PATH" 2> "$ERR_PATH"
EXIT_CODE=$?
set -e

# Shared completion oracle (decision 2026-07-16-review-verdict-closure): a verdict is
# accepted ONLY when exit code == 0 AND .err carries no auth/quota/truncation markers
# AND .out is non-empty AND its FINAL non-blank line is exactly `GATE: PASS|REVISE`.
# Earlier GATE: mentions in prose are ignored by definition. Anything else -> blocked.
if [[ -n "$LEDGER_ITEM" ]]; then
  FINAL_LINE="$(grep -v '^[[:space:]]*$' "$OUT_PATH" 2>/dev/null | tail -1 | tr -d '\r')"
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
  term_args=(--work-item "$LEDGER_ITEM" append \
    --role "$LEDGER_ROLE" --execution-role external-reviewer --provider codex \
    --status "$TERM_STATUS" --gate "$TERM_GATE" --scope "external run: ${SLUG}" \
    --event-kind terminal --launch-run-id "$LAUNCH_RUN_ID" \
    --evidence "review:${OUT_PATH}" --notes "$TERM_NOTE")
  [[ -n "$LEDGER_LANE" ]] && term_args+=(--lane "$LEDGER_LANE")
  [[ -n "$LEDGER_ARTIFACT" ]] && term_args+=(--artifact "$LEDGER_ARTIFACT")
  [[ -n "$LEDGER_EFFORT" ]] && term_args+=(--effort "$LEDGER_EFFORT")
  if [[ "$TERM_GATE" == "PASS" && ${#LEDGER_CLOSES[@]} -gt 0 ]]; then
    for c in "${LEDGER_CLOSES[@]}"; do term_args+=(--closes "$c"); done
  fi
  python "$LEDGER_HELPER" "${term_args[@]}" >/dev/null \
    || echo "WARN: could not record terminal event in $LEDGER_ITEM" >&2
fi

echo "$PROMPT_PATH"
echo "$OUT_PATH"
echo "$ERR_PATH"

exit $EXIT_CODE

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
# This wrapper drives automated headless `claude -p` runs and fails closed unless it
# detects commercial API-key/cloud auth. Subscription OAuth is not an allowed transport.
# `ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE=1` overrides the guard for commercial auth
# exposed through an undetectable path or when the operator explicitly accepts the risk.
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
#   CLAUDE_BIN                                  Claude executable or absolute path
#   CLAUDE_PROMPTS_DIR                          Output directory
#   ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE=1  Explicit ToS-guard override
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
# An explicit `--` block REPLACES these defaults wholesale, including `--model` —
# it is not merged. A partial block (e.g. only changing `--effort`) therefore
# drops the model pin entirely. To keep that from silently falling back to
# whatever model the ambient claude config selects, the wrapper validates the
# FINAL resolved flags below and refuses to launch unless an explicit --model
# and an explicit --effort <tier> are both present, regardless of whether they
# came from these defaults or from a caller-supplied `--` block.
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

# A12 guard: the FINAL resolved CLAUDE_FLAGS (the shipped default, OR a caller
# `--` block that replaces it wholesale — see the comment above the default
# assignment) must carry an explicit --model and an explicit --effort <tier>.
# Checked here, once, on whichever array the arg-parsing loop above actually
# produced, so this catches both a partial `--` block that drops the model pin
# and a hypothetical future variant that ships no default at all — either way,
# an unpinned run must never reach claude and silently resolve its model from
# ambient config.
CLAUDE_RESOLVED_MODEL=""
CLAUDE_RESOLVED_EFFORT=""
for ((_ci=0; _ci<${#CLAUDE_FLAGS[@]}; _ci++)); do
  case "${CLAUDE_FLAGS[$_ci]}" in
    --model)
      # Reject a "value" that is itself another flag (e.g. `--model --effort ...`
      # with the model name missing) so a malformed override cannot resolve to a
      # bogus non-empty model that passes the guard and gets recorded as-is.
      _candidate="${CLAUDE_FLAGS[$((_ci+1))]:-}"
      if [[ -n "$_candidate" && "$_candidate" != -* ]]; then
        CLAUDE_RESOLVED_MODEL="$_candidate"
      fi
      ;;
    --effort)
      # Exact enum match (not a regex prefix), so an unlisted tier like
      # "lowest" already cannot match "low" here — F5 does not apply to this
      # extraction, only to the Codex sibling's `-c key=value` regex form.
      case "${CLAUDE_FLAGS[$((_ci+1))]:-}" in
        low|medium|high|xhigh|max)
          CLAUDE_RESOLVED_EFFORT="${CLAUDE_FLAGS[$((_ci+1))]}"
          ;;
      esac
      ;;
  esac
done
if [[ -z "$CLAUDE_RESOLVED_MODEL" || -z "$CLAUDE_RESOLVED_EFFORT" ]]; then
  echo "FAIL: A12 violation - the resolved claude flags carry no explicit --model and/or no explicit --effort <tier>." >&2
  echo "FAIL: a '--' block replaces ALL defaults, including --model, so a partial override (e.g. only changing effort) silently drops the model pin and falls back to whatever model the ambient claude config selects — the exact outcome A12 forbids." >&2
  echo "FAIL: pass the FULL per-profile flag set after --, e.g.:" >&2
  echo "FAIL:   -- -p --output-format text --model opus --effort xhigh" >&2
  exit 1
fi

CLAUDE_CMD="${CLAUDE_BIN:-claude}"
if ! command -v "$CLAUDE_CMD" >/dev/null 2>&1; then
  echo "FAIL: claude binary '$CLAUDE_CMD' not found on PATH. Set CLAUDE_BIN if installed elsewhere." >&2
  exit 1
fi

claude_auth_truthy() {
  case "${1,,}" in
    1|true|yes) return 0 ;;
    *) return 1 ;;
  esac
}

claude_api_key_helper_configured() {
  local settings_path
  for settings_path in "${HOME:+$HOME/.claude/settings.json}" ".claude/settings.json"; do
    [[ -n "$settings_path" && -f "$settings_path" ]] || continue
    if grep -Fq '"apiKeyHelper"' "$settings_path"; then
      return 0
    fi
  done
  return 1
}

HAS_COMMERCIAL_CLAUDE_AUTH=0
if [[ -n "${ANTHROPIC_API_KEY:-}" ||
      -n "${ANTHROPIC_AUTH_TOKEN:-}" ]] ||
   claude_auth_truthy "${CLAUDE_CODE_USE_BEDROCK:-}" ||
   claude_auth_truthy "${CLAUDE_CODE_USE_VERTEX:-}" ||
   claude_api_key_helper_configured ||
   [[ "${ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE:-}" == "1" ]]; then
  HAS_COMMERCIAL_CLAUDE_AUTH=1
fi

if [[ $HAS_COMMERCIAL_CLAUDE_AUTH -ne 1 ]]; then
  cat >&2 <<'EOF'
WARNING: Refusing automated Claude launch.
Automated `claude -p` under a subscription is not permitted.
Anthropic policy: https://code.claude.com/docs/en/legal-and-compliance

Note: this checks for a commercial-auth SIGNAL in the environment; it cannot confirm
which credential the claude CLI ultimately uses. A stale ANTHROPIC_API_KEY/AUTH_TOKEN
here does NOT guarantee the CLI is not falling back to a stored subscription (OAuth)
login; make sure the commercial key is the auth claude actually resolves.

Use one of these commercial authentication paths:
  - set ANTHROPIC_API_KEY;
  - use invoke-claude-api.sh/.ps1 with SECRET.md's ANTHROPIC_AUTH_TOKEN and ANTHROPIC_BASE_URL; or
  - configure apiKeyHelper, Amazon Bedrock, or Google Vertex AI.

For commercial auth exposed through an undetectable path, or to explicitly accept the risk, set:
  ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE=1
EOF
  exit 3
fi

OUTPUT_DIR="${CLAUDE_PROMPTS_DIR:-.scratch/claude-prompts}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SLUG="${TOPIC}-${TIMESTAMP}"

mkdir -p "$OUTPUT_DIR"
PROMPT_PATH="$OUTPUT_DIR/${SLUG}.md"
OUT_PATH="$OUTPUT_DIR/${SLUG}.out"
ERR_PATH="$OUTPUT_DIR/${SLUG}.err"
PID_PATH="$OUTPUT_DIR/${SLUG}.pid"

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
  for cand in "$(dirname "$0")/agent-run-ledger.py" "scripts/agent-run-ledger.py" "$(dirname "$0")/../../../scripts/agent-run-ledger.py"; do
    [[ -f "$cand" ]] && LEDGER_HELPER="$cand" && break
  done
  if [[ -z "$LEDGER_HELPER" ]]; then
    echo "FAIL: --ledger given but scripts/agent-run-ledger.py not found" >&2
    exit 1
  fi
  LAUNCH_RUN_ID="$(date -u +%Y%m%dT%H%M%S)Z-launch-${SLUG}"
  # Both fields were already validated non-empty by the A12 guard above; reuse
  # the same resolved values here instead of re-deriving them, so the guard and
  # the recorded provenance can never key on different extractions.
  ledger_args=(--work-item "$LEDGER_ITEM" append --run-id "$LAUNCH_RUN_ID"     --role "$LEDGER_ROLE" --execution-role external-reviewer --provider claude     --status running --gate none --scope "external run: ${SLUG}"     --event-kind launch --prompt-file "$PROMPT_PATH"     --notes "wrapper-dispatched; terminal event follows the completion oracle"     --model "$CLAUDE_RESOLVED_MODEL" --effort "$CLAUDE_RESOLVED_EFFORT")
  [[ -n "$LEDGER_LANE" ]] && ledger_args+=(--lane "$LEDGER_LANE")
  [[ -n "$LEDGER_ARTIFACT" ]] && ledger_args+=(--artifact "$LEDGER_ARTIFACT")
  if ! python "$LEDGER_HELPER" "${ledger_args[@]}" >/dev/null; then
    echo "FAIL: could not record launch event in $LEDGER_ITEM" >&2
    exit 1
  fi
fi

# Process start-time marker for PID-reuse detection (Linux/MSYS /proc/<pid>/
# stat field 22, "starttime") -- duplicated from the sibling invoke-codex-
# prompt.sh / await-codex-dispatch.sh copies (no shared bash library exists in
# this script set; every wrapper here is a standalone entry point). See
# await-codex-dispatch.sh's header for the full liveness-probe rationale
# (work-items/bugs/2026-07-26-await-codex-dispatch-cannot-satisfy-its-own-
# liveness-invariant.md).
pid_start_marker() {
  local pid="$1" stat_path raw rest
  stat_path="/proc/$pid/stat"
  [[ -r "$stat_path" ]] || return 0
  raw="$(cat "$stat_path" 2>/dev/null)" || return 0
  rest="${raw##*) }"
  [[ "$rest" != "$raw" ]] || return 0
  # shellcheck disable=SC2086
  set -- $rest
  (( $# >= 20 )) || return 0
  printf '%s' "${20}"
}

# PID handoff: background the PROVIDER ITSELF (not just this wrapper) so `$!`
# captures claude's OWN pid -- bash always forks to exec a background
# command, so this is a real, separate OS process regardless of what
# `claude` resolves to. Write the `.pid` file BEFORE `wait`ing so a
# background caller can read it from launch.
set +e
(
  export ORCHESTRARIUM_DISPATCHED_REVIEW=1
  "$CLAUDE_CMD" "${CLAUDE_FLAGS[@]}" < "$PROMPT_PATH" 1> "$OUT_PATH" 2> "$ERR_PATH" &
  claude_pid=$!
  {
    printf 'pid=%s\n' "$claude_pid"
    start_marker="$(pid_start_marker "$claude_pid")"
    [[ -n "$start_marker" ]] && printf 'start=%s\n' "$start_marker"
  } > "$PID_PATH"
  wait "$claude_pid"
)
EXIT_CODE=$?
set -e

# Shared completion oracle: verdict accepted ONLY on exit 0 + clean .err + non-empty
# .out + FINAL non-blank line exactly `GATE: PASS|REVISE`; else blocked/none.
if [[ -n "$LEDGER_ITEM" ]]; then
  # `|| true`: on an EMPTY .out grep exits 1 and `pipefail` would abort the wrapper
  # here — before the blocked terminal is recorded — leaving an unsettled launch
  # (live incident 2026-07-16: codex usage-limit runs died exactly this way).
  FINAL_LINE="$(grep -v '^[[:space:]]*$' "$OUT_PATH" 2>/dev/null | tail -1 | tr -d '\r' || true)"
  # Two marker shapes, both anchored at line start so a mid-line "ERROR" inside
  # ordinary prose (e.g. the echoed prompt body) never counts:
  #   1. `ERROR: `/`FATAL: `/`API Error: ` with no timestamp (original shape).
  #   2. `<ISO8601Z timestamp> (ERROR|FATAL) <module::path>: ` -- the Rust
  #      `tracing`-crate default formatter this CLI's own MCP transport layer
  #      emits (2026-07-26 incident: `ERROR rmcp::transport::worker: worker
  #      quit with fatal:`; also observed from `codex_core::tools::router`).
  # Not covered (residual, unobserved in any real sample from this runtime):
  # non-Z timezone-offset timestamps, WARN/INFO/DEBUG/TRACE severities (by
  # design -- not fatal), a hyphenated target segment (Rust normalizes crate
  # hyphens to underscores in tracing targets), lowercase severity tokens.
  ERR_MARKERS="$(grep -cE '^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z? )?(ERROR|FATAL|API Error)(: | [A-Za-z0-9_]+(::[A-Za-z0-9_]+)*: )' "$ERR_PATH" 2>/dev/null || true)"
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
  term_args=(--work-item "$LEDGER_ITEM" append     --role "$LEDGER_ROLE" --execution-role external-reviewer --provider claude     --status "$TERM_STATUS" --gate "$TERM_GATE" --scope "external run: ${SLUG}"     --event-kind terminal --launch-run-id "$LAUNCH_RUN_ID"     --evidence "review:${OUT_PATH}" --notes "$TERM_NOTE"     --model "$CLAUDE_RESOLVED_MODEL" --effort "$CLAUDE_RESOLVED_EFFORT")
  [[ -n "$LEDGER_LANE" ]] && term_args+=(--lane "$LEDGER_LANE")
  [[ -n "$LEDGER_ARTIFACT" ]] && term_args+=(--artifact "$LEDGER_ARTIFACT")
  if [[ "$TERM_GATE" == "PASS" && ${#LEDGER_CLOSES[@]} -gt 0 ]]; then
    for c in "${LEDGER_CLOSES[@]}"; do term_args+=(--closes "$c"); done
  fi
  python "$LEDGER_HELPER" "${term_args[@]}" >/dev/null     || {
      # LOUD, not a passing WARN: a dropped terminal loses the reviewer's verdict
      # and leaves the launch unsettled, which is the exact failure this transport
      # exists to prevent. The strict checker is the backstop, but the operator
      # must see it HERE, with the recovery command.
      echo "FAIL: could not record terminal event in $LEDGER_ITEM" >&2
      echo "FAIL: the verdict in $OUT_PATH is NOT in the ledger; the launch $LAUNCH_RUN_ID stays unsettled." >&2
      echo "FAIL: record it by hand: python scripts/agent-run-ledger.py --work-item $LEDGER_ITEM append --event-kind terminal --launch-run-id $LAUNCH_RUN_ID ..." >&2
    }
fi

echo "$PROMPT_PATH"
echo "$OUT_PATH"
echo "$ERR_PATH"
echo "$PID_PATH"

exit $EXIT_CODE

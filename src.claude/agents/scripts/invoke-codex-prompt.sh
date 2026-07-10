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
#   `gpt-5.6-luna` (fast/volume/cheap tier; a distinct model, not an effort suffix):
#     -- --model gpt-5.6-luna -c model_reasoning_effort=medium
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

set +e
"$CODEX_CMD" exec --skip-git-repo-check "${CODEX_FLAGS[@]}" < "$PROMPT_PATH" 1> "$OUT_PATH" 2> "$ERR_PATH"
EXIT_CODE=$?
set -e

echo "$PROMPT_PATH"
echo "$OUT_PATH"
echo "$ERR_PATH"

exit $EXIT_CODE

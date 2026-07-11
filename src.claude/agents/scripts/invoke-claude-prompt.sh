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

set +e
"$CLAUDE_CMD" "${CLAUDE_FLAGS[@]}" < "$PROMPT_PATH" 1> "$OUT_PATH" 2> "$ERR_PATH"
EXIT_CODE=$?
set -e

echo "$PROMPT_PATH"
echo "$OUT_PATH"
echo "$ERR_PATH"

exit $EXIT_CODE

#!/usr/bin/env bash
# Run claude-api with ANTHROPIC_* loaded from the nearest Claude SECRET.md.
# Usage:
#   bash .claude/agents/scripts/invoke-claude-api.sh [claude-api args...]
#   bash .claude/agents/scripts/invoke-claude-api.sh --print-secret-path
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  bash .claude/agents/scripts/invoke-claude-api.sh [claude-api args...]
  bash .claude/agents/scripts/invoke-claude-api.sh --print-secret-path

Environment overrides:
  CLAUDE_SECRET_FILE   Explicit SECRET.md path to use
  CLAUDE_API_BIN       Claude API executable to invoke (default: claude-api)
EOF
}

add_candidate() {
  local path="$1"
  [[ -z "$path" ]] && return 0
  for existing in "${SECRET_CANDIDATES[@]:-}"; do
    [[ "$existing" == "$path" ]] && return 0
  done
  SECRET_CANDIDATES+=("$path")
}

SECRET_CANDIDATES=()
if [[ -n "${CLAUDE_SECRET_FILE:-}" ]]; then
  add_candidate "$CLAUDE_SECRET_FILE"
fi
add_candidate "$(pwd -P)/.claude/SECRET.md"
if [[ "$(basename "$PACK_ROOT")" == ".claude" ]]; then
  add_candidate "$PACK_ROOT/SECRET.md"
elif [[ "$(basename "$PACK_ROOT")" == "src.claude" ]]; then
  add_candidate "$(dirname "$PACK_ROOT")/.claude/SECRET.md"
fi
if [[ -n "${HOME:-}" ]]; then
  add_candidate "$HOME/.claude/SECRET.md"
fi
if [[ -n "${USERPROFILE:-}" ]]; then
  add_candidate "$USERPROFILE/.claude/SECRET.md"
fi
if command -v powershell.exe >/dev/null 2>&1; then
  WINDOWS_USERPROFILE="$(powershell.exe -NoProfile -Command "[Environment]::GetFolderPath('UserProfile')" 2>/dev/null | tr -d '\r')"
  if [[ -n "$WINDOWS_USERPROFILE" ]]; then
    add_candidate "$WINDOWS_USERPROFILE/.claude/SECRET.md"
    if [[ "$WINDOWS_USERPROFILE" =~ ^([A-Za-z]):\\(.*)$ ]]; then
      drive_letter="$(tr '[:upper:]' '[:lower:]' <<< "${BASH_REMATCH[1]}")"
      tail_path="${BASH_REMATCH[2]//\\//}"
      add_candidate "/mnt/$drive_letter/$tail_path/.claude/SECRET.md"
    fi
  fi
fi

SECRET_FILE=""
for candidate in "${SECRET_CANDIDATES[@]}"; do
  if [[ -f "$candidate" ]]; then
    SECRET_FILE="$candidate"
    break
  fi
done

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "$SECRET_FILE" ]]; then
  echo "FAIL: no Claude SECRET.md found. Checked: ${SECRET_CANDIDATES[*]}" >&2
  exit 1
fi

if [[ "${1:-}" == "--print-secret-path" ]]; then
  printf '%s\n' "$SECRET_FILE"
  exit 0
fi

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "FAIL: python3 or python is required to parse $SECRET_FILE" >&2
  exit 1
fi

CLAUDE_API_BIN="${CLAUDE_API_BIN:-claude-api}"
if ! command -v "$CLAUDE_API_BIN" >/dev/null 2>&1; then
  echo "FAIL: Claude API transport '$CLAUDE_API_BIN' is not available on PATH." >&2
  exit 1
fi

mapfile -t SECRET_EXPORTS < <("$PYTHON_BIN" - "$SECRET_FILE" <<'PY'
import json
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8-sig")
payload = text.strip()
if payload.startswith("```"):
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if not match:
        print(f"FAIL: could not extract JSON payload from {path}", file=sys.stderr)
        sys.exit(1)
    payload = match.group(1).strip()

try:
    data = json.loads(payload)
except json.JSONDecodeError as exc:
    print(f"FAIL: {path} is not valid JSON: {exc}", file=sys.stderr)
    sys.exit(1)

env = data.get("env") if isinstance(data, dict) else None
if not isinstance(env, dict):
    env = data if isinstance(data, dict) else None

if not isinstance(env, dict):
    print(f"FAIL: {path} must contain a JSON object or an 'env' object", file=sys.stderr)
    sys.exit(1)

required = ["ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]
missing = [key for key in required if not env.get(key)]
if missing:
    print(
        f"FAIL: {path} is missing required Claude transport keys: {', '.join(missing)}",
        file=sys.stderr,
    )
    sys.exit(1)

for key in required:
    print(f"{key}={env[key]}")
PY
)

for assignment in "${SECRET_EXPORTS[@]}"; do
  export "$assignment"
done

exec "$CLAUDE_API_BIN" "$@"

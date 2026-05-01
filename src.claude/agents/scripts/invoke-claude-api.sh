#!/usr/bin/env bash
# Run plain claude with environment variables loaded from the nearest Claude SECRET.md.
# Usage:
#   bash .claude/agents/scripts/invoke-claude-api.sh [claude args...]
#   bash .claude/agents/scripts/invoke-claude-api.sh --print-secret-path
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  bash .claude/agents/scripts/invoke-claude-api.sh [claude args...]
  bash .claude/agents/scripts/invoke-claude-api.sh --print-secret-path

Environment overrides:
  CLAUDE_SECRET_FILE   Explicit SECRET.md path to use
  CLAUDE_BIN           Claude executable or absolute path to invoke
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

resolve_claude_bin() {
  local requested="${CLAUDE_BIN:-}"
  local candidate=""
  local resolved=""

  if [[ -n "$requested" ]]; then
    if command -v "$requested" >/dev/null 2>&1; then
      command -v "$requested"
      return 0
    fi
    if [[ -f "$requested" ]]; then
      printf '%s\n' "$requested"
      return 0
    fi
    return 1
  fi

  for candidate in claude claude.cmd claude.exe; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done

  if command -v powershell.exe >/dev/null 2>&1; then
    resolved="$(powershell.exe -NoProfile -Command "(Get-Command claude,claude.exe,claude.cmd -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)" 2>/dev/null | tr -d '\r')"
    if [[ -n "$resolved" ]]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  fi

  if command -v cmd.exe >/dev/null 2>&1; then
    resolved="$(cmd.exe //c where claude 2>NUL | tr -d '\r' | head -n 1)"
    if [[ -n "$resolved" ]]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  fi

  return 1
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

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SECRET_FILE=""
for candidate in "${SECRET_CANDIDATES[@]}"; do
  if [[ -f "$candidate" ]]; then
    SECRET_FILE="$candidate"
    break
  fi
done

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

if ! CLAUDE_CMD="$(resolve_claude_bin)"; then
  CLAUDE_LABEL="${CLAUDE_BIN:-claude}"
  echo "FAIL: Claude executable '$CLAUDE_LABEL' is not available. Set CLAUDE_BIN to an executable or absolute path if it is not on the active shell PATH." >&2
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
match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
if match:
    payload = match.group(1).strip()
elif not payload.startswith(("{", "[")):
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last <= first:
        print(f"FAIL: could not extract JSON payload from {path}", file=sys.stderr)
        sys.exit(1)
    payload = text[first : last + 1].strip()

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

required = ["ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"]
missing = [key for key in required if not env.get(key)]
if missing:
    print(
        f"FAIL: {path} is missing required Claude transport keys: {', '.join(missing)}",
        file=sys.stderr,
    )
    sys.exit(1)

for key in required:
    print(f"{key}={env[key]}")
for key, value in env.items():
    if key not in required:
        print(f"{key}={value}")
PY
)

for assignment in "${SECRET_EXPORTS[@]}"; do
  export "$assignment"
done

exec "$CLAUDE_CMD" "$@"

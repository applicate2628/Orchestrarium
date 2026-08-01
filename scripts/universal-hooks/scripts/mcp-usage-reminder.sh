#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  printf '%s\n' 'FAIL: Python is required to run mcp-usage-reminder.py.' >&2
  exit 127
fi
exec "$PYTHON" "$SCRIPT_DIR/mcp-usage-reminder.py" "$@"

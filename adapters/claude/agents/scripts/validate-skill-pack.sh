#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${PYTHON:-}" ]; then
  PYTHON_CMD=$PYTHON
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD=python
else
  printf '%s\n' "FAIL: Python 3 is required by validate-skill-pack.py." >&2
  exit 127
fi
exec "$PYTHON_CMD" "$SCRIPT_DIR/validate-skill-pack.py" "$@"

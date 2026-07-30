#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then PYTHON=python3
elif command -v python >/dev/null 2>&1; then PYTHON=python
else printf '%s\n' 'FAIL: Python is required to run the installer.' >&2; exit 127
fi
exec "$PYTHON" "$SCRIPT_DIR/install.py" "$@"

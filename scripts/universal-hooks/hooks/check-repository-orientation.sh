#!/usr/bin/env bash
# Thin fail-open wrapper around check-repository-orientation.py.
# stdin: PreToolUse JSON; stdout: nothing; stderr: audit warning; exit: always 0.

set +e
script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/check-repository-orientation.py"
python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
fi
if [ -z "$python_bin" ] || [ ! -f "$helper" ]; then
  exit 0
fi
"$python_bin" "$helper"
exit 0

#!/usr/bin/env bash
# Thin wrapper around check-repository-orientation.py.
# stdin: PreToolUse JSON; stdout: nothing; stderr: audit warning.
# exit: propagates the Python helper's exit code -- 1 on a hit (a non-blocking
#       "<hook name> hook error" transcript notice so the warning is actually
#       visible; exit 0's stderr is debug-log-only per the hooks reference), 0
#       otherwise. NEVER 2 (that would block); AUDIT mode never blocks the tool
#       call regardless of exit code. Wrapper-side errors (missing python or
#       helper) still fail open to exit 0.

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
exit $?

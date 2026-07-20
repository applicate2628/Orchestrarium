#!/usr/bin/env bash
# Thin wrapper around check-typed-routing.py.
#
# Hook entry shape (PreToolUse on the Agent dispatch tool -- the subagent-dispatch
# tool captured Phase-0 as tool_name "Agent"):
#   bash <this-script>
# stdin: PreToolUse JSON envelope from Claude Code.
# stdout: nothing (AUDIT mode allows; promotion to deny is a separate step).
# stderr: an audit nudge when a `general-purpose` subagent is dispatched for work
#   that looks like typed specialist work.
# exit: propagates the Python helper's exit code -- 1 on a nudge (a non-blocking
#       "<hook name> hook error" transcript notice so the nudge is actually
#       visible; exit 0's stderr is debug-log-only per the hooks reference), 0
#       otherwise. NEVER 2 (that would block); AUDIT mode never blocks the tool
#       call regardless of exit code. Wrapper-side errors (missing python or
#       helper) still fail open to 0.
#
# All the actual logic lives in the .py sibling. If no Python interpreter is
# available or the helper fails for any reason, we exit 0 (fail-open).

set +e

script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/check-typed-routing.py"

python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
fi
if [ -z "$python_bin" ]; then
  exit 0
fi
if [ ! -f "$helper" ]; then
  exit 0
fi

"$python_bin" "$helper"
exit $?

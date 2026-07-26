#!/usr/bin/env bash
# Thin wrapper around check-typed-routing.py.
#
# Hook entry shape (PreToolUse on the Agent dispatch tool -- the subagent-dispatch
# tool captured Phase-0 as tool_name "Agent"):
#   bash <this-script>
# stdin: PreToolUse JSON envelope from Claude Code.
# stdout: on a nudge, one line of JSON -- {"hookSpecificOutput":{"hookEventName":
#   "PreToolUse","additionalContext":"..."}} -- the model-visible nudge when a
#   `general-purpose` subagent is dispatched for work that looks like typed
#   specialist work (see hook_common.emit_advisory); nothing otherwise.
# stderr: nothing. The prior stderr-plus-exit-1 delivery was measured to reach
#   nobody on Claude Code; see work-items/bugs/2026-07-26-mcp-reminder-uses-
#   the-once-per-session-form-its-sibling-calls-broken.md.
# exit: propagates the Python helper's exit code, which is now ALWAYS 0 --
#       AUDIT mode never blocks and the nudge travels via the stdout JSON
#       above, not a non-zero exit. Wrapper-side errors (missing python or
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

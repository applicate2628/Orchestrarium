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
# exit: propagates the Python helper's exit code. On a normal run (hit or
#       miss) that is 0 -- AUDIT mode never blocks and the nudge travels via
#       the stdout JSON above, not a non-zero exit. It is NOT always 0: an
#       unimportable hook_common now surfaces as an uncaught ImportError --
#       exit 1 and a traceback naming the module on stderr, the
#       detectability the fix relies on -- instead of a silent exit 0. Still
#       never exit 2 (AUDIT mode never blocks a PreToolUse tool call on
#       Claude Code -- the only runtime this Claude-only hook runs on; only
#       exit 2 does). Per the official hooks docs exit 1 is non-blocking
#       (hook_common.emit_advisory's own docstring; work-items/bugs/2026-07-
#       26-mcp-reminder-uses-the-once-per-session-form-its-sibling-calls-
#       broken.md). Wrapper-side errors (missing python or helper) still
#       fail open to exit 0.
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

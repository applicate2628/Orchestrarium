#!/usr/bin/env bash
# Thin wrapper around check-machine-local-path.py.
#
# Hook entry shape (PreToolUse on Edit/Write/NotebookEdit/apply_patch):
#   bash <this-script>
# stdin: PreToolUse JSON envelope from Claude Code or Codex.
# stdout: on a hit, one line of JSON -- {"hookSpecificOutput":{"hookEventName":
#   "PreToolUse","additionalContext":"..."}} -- the model-visible advisory if a
#   machine-local path is written to a tracked file (see hook_common.emit_advisory);
#   nothing otherwise.
# stderr: nothing. The prior stderr-plus-exit-1 delivery was measured to reach
#   nobody on either provider line; see work-items/bugs/2026-07-26-mcp-reminder-
#   uses-the-once-per-session-form-its-sibling-calls-broken.md.
# exit: propagates the Python helper's exit code, which is now ALWAYS 0 --
#       AUDIT mode never blocks and the advisory travels via the stdout JSON
#       above, not a non-zero exit. Wrapper-side errors (missing python or
#       helper) still fail open to exit 0.
#
# All the actual logic lives in the .py sibling. If no Python interpreter is
# available or the helper fails for any reason, we exit 0 (fail-open).

set +e

script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/check-machine-local-path.py"

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

#!/usr/bin/env bash
# Thin wrapper around check-no-trash-in-repo.py.
#
# Hook entry shape (PreToolUse on Edit/Write/NotebookEdit/apply_patch and Bash):
#   bash <this-script>
# stdin: PreToolUse JSON envelope from Claude Code or Codex.
# stdout: nothing (AUDIT mode allows; promotion to deny is a separate step).
# stderr: an audit warning if an unrequested `git worktree add` is run (a single add
#   ending with the exact `# orchestrarium:requested-isolation-worktree` marker is exempt).
# exit: propagates the Python helper's exit code -- 1 on a hit (a non-blocking
#       "<hook name> hook error" transcript notice so the warning is actually
#       visible; exit 0's stderr is debug-log-only per the hooks reference), 0
#       otherwise. NEVER 2 (that would block); AUDIT mode never blocks the tool
#       call regardless of exit code. Wrapper-side errors (missing python or
#       helper) still fail open to exit 0.
#
# All the actual logic lives in the .py sibling. If no Python interpreter is
# available or the helper fails for any reason, we exit 0 (fail-open).

set +e

script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/check-no-trash-in-repo.py"

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

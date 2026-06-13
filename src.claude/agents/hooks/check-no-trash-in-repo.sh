#!/usr/bin/env bash
# Thin wrapper around check-no-trash-in-repo.py.
#
# Hook entry shape (PreToolUse on Edit/Write/NotebookEdit/apply_patch and Bash):
#   bash <this-script>
# stdin: PreToolUse JSON envelope from Claude Code or Codex.
# stdout: nothing (AUDIT mode allows; promotion to deny is a separate step).
# stderr: an audit warning if a personal-workflow dir is created inside a repo.
# exit: always 0 (fail-open on any internal error; AUDIT mode never blocks).
#
# All the actual logic lives in the .py sibling. If python3 is missing or the
# helper fails for any reason, we exit 0 (fail-open).

set +e

script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/check-no-trash-in-repo.py"

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi
if [ ! -f "$helper" ]; then
  exit 0
fi

python3 "$helper"
exit 0

#!/usr/bin/env bash
# Thin wrapper around check-bugfix-discipline.py.
#
# Hook entry shape (PreToolUse on Edit/Write/NotebookEdit):
#   bash <this-script>
# stdin: PreToolUse JSON envelope from Claude Code or Codex.
# stdout: deny JSON if bug-context detected without /agents-bugfix discipline;
#         nothing otherwise.
# exit: always 0 (decision carried by stdout payload, not exit code; fail-open
#       on any internal error so legitimate work is never blocked).
#
# All the actual logic lives in the .py sibling because JSONL transcript
# parsing is much cleaner in python than in bash. If python3 is missing or
# the helper fails for any reason, we exit 0 (fail-open).

set +e

script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/check-bugfix-discipline.py"

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi
if [ ! -f "$helper" ]; then
  exit 0
fi

python3 "$helper"
exit 0

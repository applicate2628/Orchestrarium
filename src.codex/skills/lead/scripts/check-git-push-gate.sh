#!/usr/bin/env bash
# Thin wrapper around check-git-push-gate.py.
#
# Hook entry shape (PreToolUse on Bash):
#   bash <this-script>
# stdin: PreToolUse JSON envelope from Claude Code or Codex.
# stdout: deny JSON if a `git push` is detected without the per-turn user
#         approval marker or scan-evidence-plus-instruction; nothing otherwise.
# exit: always 0 (decision carried by stdout payload, not exit code; fail-open
#       on any internal error so legitimate work is never blocked).
#
# All the actual logic lives in the .py sibling because shell-aware command
# parsing and JSONL transcript parsing are much cleaner in python than in
# bash. If no Python interpreter is available or the helper fails for any
# reason, we exit 0 (fail-open).

set +e

script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/check-git-push-gate.py"

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
exit 0

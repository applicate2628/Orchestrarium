#!/usr/bin/env bash
# Thin wrapper around check-passive-polling-stop.py.
#
# Hook entry shape (Stop):
#   bash <this-script>
# stdin: Stop JSON envelope from Claude Code or Codex.
# stdout: block JSON if a passive-polling stop is detected without a relevant
#         current-turn state probe; nothing otherwise.
# exit: always 0 (decision carried by stdout payload, not exit code; fail-open
#       on any internal error so legitimate work is never blocked).

set +e

script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/check-passive-polling-stop.py"

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi
if [ ! -f "$helper" ]; then
  exit 0
fi

python3 "$helper"
exit 0

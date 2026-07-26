#!/usr/bin/env bash
# Thin wrapper around check-work-items-archival-stop.py.
#
# This filename is a Codex trust-pinned wire identifier and stays unchanged
# even though the .py helper now hosts TWO invariants from the
# workitem_sentinels.py registry, not one: SEN-0 (archival orphan -- this
# hook's original sole behaviour) and SEN-1 (dual-state item: a slug present
# in BOTH work-items/active/ and work-items/archive/). A third invariant
# (SEN-2, delivery drought) and a third response tier (HALT) were designed
# and then withdrawn before release -- see check-work-items-archival-stop.py's
# own docstring and references-codex/stop-hook-halting-primitives.md for why.
#
# Hook entry shape (Stop):
#   bash <this-script>
# stdin: Stop JSON envelope from Claude Code or Codex.
# stdout: a RESOLVE ({"decision": "block", ...}) or
#         NOTICE ({"systemMessage": ...}) payload if any invariant fires;
#         nothing otherwise. There is no run-terminating tier on either
#         provider line (HALT was removed).
# exit: always 0 (decision carried by stdout payload, not exit code; fail-open
#       on any internal error so legitimate work is never blocked).

set +e

script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/check-work-items-archival-stop.py"

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

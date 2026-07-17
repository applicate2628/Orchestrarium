#!/usr/bin/env bash
# Thin wrapper around check-scratch-valuables.py.
#
# Hook entry shape (SessionStart, no matcher -- fires on startup / resume /
# clear / compact, same as mcp-usage-reminder):
#   bash <this-script>
# stdin: SessionStart JSON envelope from Claude Code or Codex.
# stdout: a hookSpecificOutput context block IF valuable-looking files have
#         lingered in .scratch/ past the age threshold; nothing otherwise
#         (byte-silent, same convention as agents-mode-reminder).
# exit: always 0 (fail-open on any internal error; this reminder must never
#       block a session).
#
# All the actual logic lives in the .py sibling -- this wrapper only pipes
# stdin through and propagates output. If no Python interpreter is available
# or the helper is missing, we exit 0 (fail-open).

set +e

script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/check-scratch-valuables.py"

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

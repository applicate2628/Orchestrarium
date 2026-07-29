#!/usr/bin/env python3
"""SessionStart hook -- re-injects an MCP / tools usage reminder into the
model's context at every session start AND after every compaction. This is
the Python twin of mcp-usage-reminder.sh / mcp-usage-reminder.ps1, existing
so a hook installer MAY register `python mcp-usage-reminder.py` directly
instead of `bash mcp-usage-reminder.sh` / `powershell -File
mcp-usage-reminder.ps1`.

WHY THIS TWIN EXISTS (measured, not assumed). Profiled on the operator's real
project (median of 3): `mcp-usage-reminder.ps1` costs 234.7ms end-to-end to
print 2247 bytes of STATIC text -- there is no per-invocation logic at all,
the entire cost is `powershell.exe -NoProfile` process startup. A bare
`python -c pass` was separately measured on that same machine at 31ms
end-to-end, versus 185ms for a bare `powershell.exe -NoProfile` doing
nothing -- see the platform-engineer implementation report for this file's
own measured end-to-end cost via a real invocation. `.sh`/`.ps1` themselves
are UNCHANGED by this file's existence -- see their own headers; this is
additive, not a replacement. Whether either wrapper is still registered
anywhere is an installer decision, not this file's.

Generic ON PURPOSE, same as the .sh/.ps1 siblings: names NO specific MCP
server (a hardcoded machine-local list would be wrong to ship). The agent
discovers the actual connected servers via tool discovery.

BYTE-PARITY CONTRACT: the reminder text below is copied verbatim (including
the literal UTF-8 em-dash, not an escaped \\u2014) from the .sh sibling's
heredoc, which is itself the un-substituted form of the .ps1 sibling's
$emDash-templated string -- both already produce the identical parsed JSON
value (verified this session: extracting both sides' `additionalContext`
via `json.loads` and comparing equal). This file emits the payload via
`hook_common.emit_session_start_context`, which reproduces the same
`hookSpecificOutput` shape with compact (no-whitespace) separators and a
literal (non-escaped) UTF-8 em-dash -- see that function's docstring for the
full byte-parity reasoning and why `hook_common.emit_advisory` (a sibling
function with a DIFFERENT, already-shipped ensure_ascii=True contract for
its own PreToolUse callers) is not reused here instead.

No stdin dependency: like both the .sh and .ps1 siblings, this hook ignores
its own envelope entirely (no `agent_id`/subagent check, no `cwd` read) --
the reminder is unconditional and identical for every SessionStart source
(startup / resume / clear / compact) and every caller, including a dispatched
subagent. Fail-open: any error is swallowed and this still exits 0.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_common import emit_session_start_context
from mcp_continuity_policy import SESSION_START_CONTEXT


def main() -> int:
    emit_session_start_context(SESSION_START_CONTEXT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

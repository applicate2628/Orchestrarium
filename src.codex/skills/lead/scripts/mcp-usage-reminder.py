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

REMINDER = (
    '[MCP / tools reminder - re-shown at session start and after every compaction]\nMCP servers may be connected in this environment. For codebase, architecture, API/docs, search, browser, debugger, profiler, or repository-understanding tasks, make MCP/tool-discovery an explicit checkpoint before falling back to ad-hoc shell reads.\nMCP tools load on demand: use the platform\'s tool discovery (e.g. ToolSearch) to see the connected servers and load a tool\'s schema, then call the relevant tool. If a relevant MCP is unavailable or broken, say so briefly instead of silently substituting a weaker path.\nCONNECTED but uninitialized is not unavailable: do NOT skip a connected MCP reporting "not initialized", "no index", "empty", or "no data yet". Many servers require or build their own index/state on first use — when they report no index, INITIALIZE them per the server\'s own instructions (e.g. run a code-graph server\'s init / check its status; codegraph builds its initial index via `codegraph init`, then a file-watcher keeps it fresh) and use or await the result — never silently substitute ad-hoc shell/grep. Only a genuinely absent server (not connected, not installed, or absent from tool discovery) may be skipped with an explanation.\nWhen mcpMode: force is active, relevant MCP use is a standing instruction. Under mcpMode: auto, still consider MCP first when it fits the task and record why it was skipped if the task explicitly asked for MCP.\nHigh-value categories when present: semantic code navigation and code-graph, Repomix or repository packers, language-server / LSP, current library / framework / API docs (use these instead of answering API questions from memory), debuggers and profilers, browser automation, memory, search, and fetch utilities.\nThis STILL APPLIES AFTER COMPACTION - do not forget MCP just because the context was summarized.\nSUBAGENTS: dispatched agents inherit the runtime tool surface. In the dispatch prompt, explicitly allow relevant MCP discovery/use within the assigned role, scope, and safety limits; do not accidentally hide MCP availability, but keep any deliberate tool limits honest.'
)


def main() -> int:
    emit_session_start_context(REMINDER)
    return 0


if __name__ == "__main__":
    sys.exit(main())

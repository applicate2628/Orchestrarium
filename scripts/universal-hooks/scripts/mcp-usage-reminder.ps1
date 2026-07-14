# SessionStart hook -- re-injects an MCP / tools usage reminder into the model's context
# at every session start AND after every compaction. Registered with NO matcher, so it
# fires on every SessionStart source (startup / resume / clear / compact). Structured
# SessionStart JSON adds the reminder as model context on both Claude Code and Codex.
#
# Generic ON PURPOSE: it names NO specific MCP server (a hardcoded machine-local list would
# be wrong to ship). The agent discovers the actual connected servers via tool discovery.
# ASCII-only output so it never mojibakes across console codepages. Fail-open; exits 0.
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$reminder = @'
[MCP / tools reminder - re-shown at session start and after every compaction]
MCP servers may be connected in this environment. For codebase, architecture, API/docs, search, browser, debugger, profiler, or repository-understanding tasks, make MCP/tool-discovery an explicit checkpoint before falling back to ad-hoc shell reads.
MCP tools load on demand: use the platform's tool discovery (e.g. ToolSearch) to see the connected servers and load a tool's schema, then call the relevant tool. If a relevant MCP is unavailable or broken, say so briefly instead of silently substituting a weaker path.
When mcpMode: force is active, relevant MCP use is a standing instruction. Under mcpMode: auto, still consider MCP first when it fits the task and record why it was skipped if the task explicitly asked for MCP.
High-value categories when present: semantic code navigation and code-graph, Repomix or repository packers, language-server / LSP, current library / framework / API docs (use these instead of answering API questions from memory), debuggers and profilers, browser automation, memory, search, and fetch utilities.
This STILL APPLIES AFTER COMPACTION - do not forget MCP just because the context was summarized.
SUBAGENTS: dispatched agents inherit the runtime tool surface. In the dispatch prompt, explicitly allow relevant MCP discovery/use within the assigned role, scope, and safety limits; do not accidentally hide MCP availability, but keep any deliberate tool limits honest.
'@

try {
    $payload = [ordered]@{
        hookSpecificOutput = [ordered]@{
            hookEventName = "SessionStart"
            additionalContext = $reminder
        }
    }
    $json = $payload | ConvertTo-Json -Compress -Depth 4 -ErrorAction Stop
    if ($json) { [Console]::Out.WriteLine($json) }
} catch {}
exit 0

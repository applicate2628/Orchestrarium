#!/usr/bin/env bash
# SessionStart hook -- re-injects an MCP / tools usage reminder into the model's context
# at every session start AND after every compaction. Registered with NO matcher, so it
# fires on every SessionStart source (startup / resume / clear / compact). Plain stdout is
# added as model context on both Claude Code and Codex (Codex: "Plain text on stdout is
# added as extra developer context").
#
# Generic ON PURPOSE: it names NO specific MCP server (a hardcoded machine-local list would
# be wrong to ship). The agent discovers the actual connected servers via tool discovery.
# Fail-open: never blocks; always exits 0.
cat <<'EOF'
[MCP / tools reminder - re-shown at session start and after every compaction]
You have MCP servers connected in this environment. Prefer the right MCP tool over ad-hoc Bash/grep/Read when one fits the task.
MCP tools load on demand: use the platform's tool discovery (e.g. ToolSearch) to see the connected servers and load a tool's schema, then call it.
High-value categories when present: semantic code navigation and code-graph, language-server / LSP, current library / framework / API docs (use these instead of answering API questions from memory), debuggers and profilers, browser automation, and memory / search / fetch utilities.
This STILL APPLIES AFTER COMPACTION - do not forget MCP just because the context was summarized.
SUBAGENTS: when you dispatch one, do NOT narrow its tools. Every subagent inherits all available tools, including every connected MCP server, and may use any of them at its own discretion - say so in the dispatch prompt instead of restricting it.
EOF
exit 0

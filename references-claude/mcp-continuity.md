# MCP Continuity — Claude Code Addendum

Canonical shared semantics: [shared/references/mcp-continuity.md](../shared/references/mcp-continuity.md).

## Claude Code runtime binding

Claude Code installs the three adapters below its agent pack:

- `~/.claude/agents/scripts/mcp-usage-reminder.py` on `SessionStart`
- `~/.claude/agents/scripts/turn-anchor-reminder.py` on `UserPromptSubmit`
- `~/.claude/agents/scripts/check-mcp-momentum.py` on `PreToolUse`

The momentum entry uses the exact matcher `Grep|Bash|PowerShell|shell_command|exec_command`. Native `Grep` and the four shell-shaped tool names enter the same shared classifier; `exec_command` reads `cmd` and accepts `command` as a compatibility shape.

The adapter forwards the raw envelope `cwd` unchanged. The shared policy alone finds the nearest repository root and grants an exemption only to the four exact repository-root subtrees; a matching segment at any other depth, an unavailable coordinate, or one non-exempt scope grants no exemption.

For `mcpMode: auto` and envelopes carrying `agent_id`, a qualifying search
receives a model-visible, nonblocking advisory through
`hookSpecificOutput.additionalContext`. A root conversation in effective
`mcpMode: force` receives the `[MCP-FORCE-ADVISORY]` reminder through the same
channel. The force duty still requires runtime tool discovery, the relevant
tool schema, and use of a fitting MCP, including selected-root and currentness
checks and the existing alternative-path restrictions. Runtime discovery is
the only availability source; configured names do not establish availability.
The advisory explicitly leaves compliance undetermined, grants no permission,
and does not override host refusals. Unresolved modes receive the stable
`[MCP-FORCE-MODE-UNRESOLVED]` diagnostic advisory. Named tools in documentation
are non-normative examples and never selection logic. Internal errors fail
open. The policy support module is installed beside the scripts but has no
hook registration of its own.

Registration and source validation prove the event path, not installed force
advisory delivery. A post-install firing check must confirm the installed
source identity and current force advisory on a representative qualifying
search; that confirms delivery, not compliance or model obedience.

## Terms and Abbreviations

- `MCP`: Model Context Protocol.
- `PreToolUse`: the hook event fired before an admitted tool call.

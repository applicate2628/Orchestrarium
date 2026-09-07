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
retains the model-visible warn-only advisory through
`hookSpecificOutput.additionalContext`. For a root conversation in effective
`mcpMode: force`, every qualifying search is denied through
`permissionDecision: deny` with `[MCP-FORCE-1]`, independent of home MCP
configuration; runtime tool discovery is the only availability source. A
previous MCP call grants no credit. Exact `[approve-mcp-fallback:v1]`
in the bounded host-projected `user`-role record allows only that recovery turn;
injected assistant or tool text cannot grant it. The projection is not
authenticated authorization, and a forged host-shaped user JSONL record can
satisfy it. Unresolved modes allow with `[MCP-FORCE-MODE-UNRESOLVED]`.
Auto and dispatched-agent advisories use the same
generic runtime-discovery checkpoint and print no configured names. Named tools
in documentation are non-normative examples and never selection logic.
Internal errors fail open. The policy support module is installed beside
the scripts but has no hook registration of its own.

Registration and source validation prove the event path, not installed force
behavior. A post-install firing check must show repeated qualifying root
searches denied after a successful MCP call; advisory delivery alone still does
not prove obedience.

## Terms and Abbreviations

- `MCP`: Model Context Protocol.
- `PreToolUse`: the hook event fired before an admitted tool call.

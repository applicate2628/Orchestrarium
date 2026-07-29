# MCP Continuity — Claude Code Addendum

Canonical shared semantics: [shared/references/mcp-continuity.md](../shared/references/mcp-continuity.md).

## Claude Code runtime binding

Claude Code installs the three adapters below its agent pack:

- `~/.claude/agents/scripts/mcp-usage-reminder.py` on `SessionStart`
- `~/.claude/agents/scripts/turn-anchor-reminder.py` on `UserPromptSubmit`
- `~/.claude/agents/hooks/check-mcp-momentum.py` on `PreToolUse`

The momentum entry uses the exact matcher `Grep|Bash|PowerShell|shell_command|exec_command`. Native `Grep` and the four shell-shaped tool names enter the same shared classifier; `exec_command` reads `cmd` and accepts `command` as a compatibility shape.

The adapter forwards the raw envelope `cwd` unchanged. The shared policy alone finds the nearest repository root and grants an exemption only to the four exact repository-root subtrees; a matching segment at any other depth, an unavailable coordinate, or one non-exempt scope grants no exemption.

The hook evaluates root and `agent_id` envelopes identically. A qualifying search emits a model-visible warn-only advisory through `hookSpecificOutput.additionalContext`; hits and misses exit 0, no path blocks with exit 2, and internal errors fail open. The policy support module is installed beside the scripts but has no hook registration of its own.

Registration and source validation prove the event path, not obedience. A post-install firing check is still required before claiming installed behavior, and even a delivered advisory cannot prove that the model followed it.

## Terms and Abbreviations

- `MCP`: Model Context Protocol.
- `PreToolUse`: the hook event fired before an admitted tool call.

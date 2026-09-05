# MCP Continuity — Codex Addendum

Canonical shared semantics: [shared/references/mcp-continuity.md](../shared/references/mcp-continuity.md).

## Codex runtime binding

Codex installs the three adapters below the Lead skill:

- `$HOME/.agents/skills/lead/scripts/mcp-usage-reminder.py` on `SessionStart`
- `$HOME/.agents/skills/lead/scripts/turn-anchor-reminder.py` on `UserPromptSubmit`
- `$HOME/.agents/skills/lead/hooks/check-mcp-momentum.py` on `PreToolUse`

The momentum entry uses the exact matcher `Grep|Bash|PowerShell|shell_command|exec_command`. The broad matcher is defensive because the tool name exposed by Codex has varied by runtime version; the adapter still admits only those five names and applies the shared classifier to the actual envelope. For `exec_command`, the canonical command field is `cmd`, with `command` accepted as a compatibility input.

The adapter forwards the raw envelope `cwd` unchanged. The shared policy alone finds the nearest repository root and grants an exemption only to the four exact repository-root subtrees; a matching segment at any other depth, an unavailable coordinate, or one non-exempt scope grants no exemption.

The hook does not skip an envelope merely because `agent_id` is present. Root and dispatched-agent hits are model-visible warn-only advisories carried through `hookSpecificOutput.additionalContext`; both hit and miss exit 0, and internal errors fail open. Every qualifying hit emits the same generic runtime-discovery checkpoint without reading home MCP configuration or printing configured server names. Named tools in documentation are non-normative examples and never selection logic. The policy support module is copied beside the scripts but is not registered as a hook stem.

Codex marks a changed registration identity as untrusted. Because this release changes the existing MCP-momentum matcher, an operator must reinstall and explicitly trust the affected entry before installed firing can be claimed. Source tests and validators do not verify installed dogfood.

## Terms and Abbreviations

- `MCP`: Model Context Protocol.
- `PreToolUse`: the hook event fired before an admitted tool call.

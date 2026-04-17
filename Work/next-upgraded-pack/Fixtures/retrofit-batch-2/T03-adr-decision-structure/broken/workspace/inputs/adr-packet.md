M03 ADR packet

Decision question:
- keep provider order at the provider level
- keep fallback behavior as provider-local path notes

Admitted rules:
- do not invent providers outside `codex | claude | gemini`
- `claude-api` is a secondary Claude transport, not a fourth provider
- transport keys change command environment, not provider identity
- do not propose MCP scoring in this decision

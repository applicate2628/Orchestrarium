---
name: external-worker
description: Implement approved work through an external provider when the routing decision selects the external adapter for an eligible implementer role. Use when Gemini CLI needs a universal implementation adapter with fail-fast handling and no role-internal fallback.
---

# External Worker

Use the shared Gemini dispatch contract in [../lead/external-dispatch.md](../lead/external-dispatch.md).

## Rules

- Implement-side only.
- No silent internal fallback.
- Respect the approved change surface.
- Preserve the replaced internal role as provenance.

## Gemini-line provider rules

- Read `.gemini/.agents-mode` first, then legacy `.gemini/.consultant-mode`.
- `externalProvider: auto` keeps provider-backed external dispatch explicit on the Gemini line.
- `externalProvider: codex` resolves to Codex CLI explicitly.
- `externalProvider: claude` resolves to Claude CLI explicitly.
- If Claude is selected, honor `externalClaudeSecretMode`.
- `externalProvider: gemini` is invalid on the Gemini line.

## Return

Return one implementation artifact with:

1. Summary
2. Changed surface
3. Verification evidence or blocked reason
4. Risks / unknowns
5. Gate: PASS | REVISE | BLOCKED:dependency

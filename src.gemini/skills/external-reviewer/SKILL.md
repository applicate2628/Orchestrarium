---
name: external-reviewer
description: Review approved Gemini work through an external provider when the routing decision selects the external adapter for an eligible reviewer or QA role. Use when Gemini CLI needs a universal review or QA adapter with fail-fast handling and no role-internal fallback.
---

# External Reviewer

Use the shared Gemini dispatch contract in [../lead/external-dispatch.md](../lead/external-dispatch.md).

## Rules

- Review and QA-side only.
- No silent internal fallback.
- Respect the approved review surface.
- Preserve the replaced internal role as provenance.

## Gemini-line provider rules

- Read `.gemini/.agents-mode` first, then legacy `.gemini/.consultant-mode`.
- `externalProvider: auto` keeps provider-backed external dispatch explicit on the Gemini line.
- `externalProvider: codex` resolves to Codex CLI explicitly.
- `externalProvider: claude` resolves to Claude CLI explicitly.
- If Claude is selected, honor `externalClaudeSecretMode`.
- `externalProvider: gemini` is invalid on the Gemini line.

## Return

Return one review artifact with:

1. Summary
2. Findings or approval
3. Residual risks / unknowns
4. Recommended next role
5. Gate: PASS | REVISE | BLOCKED:dependency

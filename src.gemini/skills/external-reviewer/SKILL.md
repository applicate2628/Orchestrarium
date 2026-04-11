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

- Read and normalize `.gemini/.agents-mode` to the current canonical format before trusting its flags.
- Honor `.gemini/.agents-mode`, including `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`.
- `externalOpinionCounts` governs distinct-provider opinions for one lane; it does not cap how many same-provider review instances may run in parallel for different disjoint lanes or slices.
- `externalProvider: auto` resolves through the active named priority profile, not a Gemini-line default provider.
- `externalPriorityProfile` defaults to `balanced`; `gemini-crosscheck` is the profile that keeps Gemini inside non-visual review cross-check lanes.
- `externalProvider: codex` resolves to Codex CLI explicitly.
- `externalProvider: claude` resolves to Claude CLI explicitly.
- If Claude is selected, honor `externalClaudeSecretMode`.
- If Claude is selected, honor `externalClaudeApiMode`.
- This adapter is a direct external launch contract. Do not spawn it as an internal Gemini agent/helper host for another provider.
- `externalProvider: gemini` is allowed only as an explicit self-provider override.
- Visual review lanes for image, icon, or decorative work are the shared-matrix cases where Gemini should be preferred when that routing remains honest.
- Same-provider Gemini routing must be explicit; ordinary `auto` must still avoid self-bounce.
- If the active lane policy requests more than one external review or QA opinion, the lead may launch more than one eligible external reviewer in parallel and aggregate the returned review artifacts fail closed.
- Multiple simultaneous instances of this adapter may target the same provider when each instance owns a different admitted artifact or disjoint slice and the provider runtime supports concurrent non-interactive execution.

## Return

Return one review artifact with:

1. Summary
2. Findings or approval
3. Residual risks / unknowns
4. Recommended next role
5. Gate: PASS | REVISE | BLOCKED:dependency

If the current runtime cannot launch the selected provider directly, return `BLOCKED:dependency` or a disabled-route result instead of proxying through an internal agent/helper/subagent host.

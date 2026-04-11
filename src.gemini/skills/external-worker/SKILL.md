---
name: external-worker
description: Execute approved worker-side role work through an external provider when the routing decision selects the external adapter for an eligible non-owner, non-review role. Use when Gemini CLI needs a universal worker-side adapter with fail-fast handling and no role-internal fallback.
---

# External Worker

Use the shared Gemini dispatch contract in [../lead/external-dispatch.md](../lead/external-dispatch.md).

## Rules

- Worker-side only.
- No silent internal fallback.
- Respect the approved role contract and change surface.
- Preserve the replaced internal worker role as provenance.

## Gemini-line provider rules

- Read and normalize `.gemini/.agents-mode` to the current canonical format before trusting its flags.
- Honor `.gemini/.agents-mode`, including `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`.
- `externalOpinionCounts` governs distinct-provider opinions for one lane; it does not cap how many same-provider worker instances may run in parallel for different disjoint lanes or slices.
- `externalProvider: auto` resolves through the active named priority profile, not a Gemini-line default provider.
- `externalPriorityProfile` defaults to `balanced`; `gemini-crosscheck` is a valid profile when the lane policy wants Gemini to appear in a non-visual cross-check set.
- `externalProvider: codex` resolves to Codex CLI explicitly.
- `externalProvider: claude` resolves to Claude CLI explicitly.
- If Claude is selected, honor `externalClaudeSecretMode`.
- If Claude is selected, honor `externalClaudeApiMode`.
- This adapter is a direct external launch contract. Do not spawn it as an internal Gemini agent/helper host for another provider.
- `externalProvider: gemini` is allowed only as an explicit self-provider override.
- Image generation, icon work, decorative visual polish, and other clearly visual worker-side lanes are the shared-matrix cases where Gemini should be preferred when that routing remains honest.
- Same-provider Gemini routing must be explicit; ordinary `auto` must still avoid self-bounce.
- If the active lane policy requests more than one external worker-side opinion, the lead may launch more than one eligible external worker in parallel and aggregate the returned worker artifacts fail closed.
- Multiple simultaneous instances of this adapter may target the same provider when each instance owns a different admitted artifact or disjoint slice and the provider runtime supports concurrent non-interactive execution.

## Return

Return one worker artifact with:

1. Summary
2. Changed surface
3. Verification evidence or blocked reason
4. Risks / unknowns
5. Gate: PASS | REVISE | BLOCKED:dependency

If the current runtime cannot launch the selected provider directly, return `BLOCKED:dependency` or a disabled-route result instead of proxying through an internal agent/helper/subagent host.

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

- Read and normalize `.gemini/.agents-mode.yaml` to the current canonical format before trusting its flags.
- If the canonical file is missing, read legacy `.gemini/.agents-mode` as compatibility input only, normalize it forward into `.gemini/.agents-mode.yaml`, and do not recreate the legacy file.
- Honor `.gemini/.agents-mode.yaml`, including `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`.
- `externalOpinionCounts` governs distinct-provider opinions for one lane; it does not cap how many same-provider review instances may run in parallel for different disjoint lanes or slices.
- `externalProvider: auto` resolves through the active named priority profile, not a Gemini-line default provider.
- `externalPriorityProfile` defaults to `balanced`; `gemini-crosscheck` is the profile that keeps Gemini inside non-visual review cross-check lanes.
- `externalProvider: codex` resolves to Codex CLI explicitly.
- `externalProvider: claude` resolves to Claude CLI explicitly.
- Honor `externalModelMode` first when Gemini is selected: `runtime-default` keeps Gemini on its runtime default model/profile. Under `pinned-top-pro`, `externalGeminiFallbackMode` controls the explicit Gemini path: `disabled` keeps `gemini-3.1-pro` only, `auto` starts on `gemini-3.1-pro` and allows one retry on `gemini-3-flash` only for quota, limit, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style Gemini failures, and `force` starts on `gemini-3-flash` immediately.
- Treat `gemini-3-flash` as a bounded mechanical overflow path only. `externalGeminiFallbackMode: force` is for tightly scoped low-reasoning work, not for broad reasoning or cleanup just to save tokens.
  - If Claude is selected, honor `externalClaudeSecretMode`.
- If Claude is selected, honor `externalClaudeApiMode`.
- Treat the secret-backed Claude wrapper as the approved economical near-full-strength Claude transport. `externalClaudeApiMode: force` is an explicit budget choice as well as a limit fallback.
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

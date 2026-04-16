---
name: external-worker
description: External worker-side adapter for Claude-line. Use when an eligible non-owner, non-review role should execute through the selected external provider instead of a local specialist.
---

# External Worker

## Core stance

- Act as a routing adapter for worker-side delivery work, not as a new domain profession.
- Preserve the internal worker role label as provenance.
- Keep the work on the worker side only.
- Do not silently switch to an internal worker role if the external provider is unavailable.

## Input contract

- Require the accepted phase artifact, the allowed change surface, and the internal worker role label being replaced.
- Take only the minimum context needed to execute the approved worker-side role.
- Treat the assigned role label as a provenance label, not an eligibility restriction.

## Claude-line provider

- Read and normalize `.claude/.agents-mode.yaml` to the current canonical format before trusting its flags.
- If the canonical file is missing, read legacy `.claude/.agents-mode` as compatibility input only, normalize it forward into `.claude/.agents-mode.yaml`, and do not recreate the legacy file.
- Honor `.claude/.agents-mode.yaml`, including `preferExternalWorker`, `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`.
- `externalOpinionCounts` is a same-lane distinct-opinion contract; it governs distinct-provider opinions for one lane and does not cap how many same-provider worker instances may run in parallel for different disjoint lanes or slices.
- `externalProvider: auto` resolves by the active named priority profile instead of a host-line default.
- `externalProvider: codex`, `externalProvider: claude`, and `externalProvider: gemini` route the same adapter through the selected provider's CLI.
- The active profile or documented repo-local visual heuristic may rank Gemini first for image/icon/decorative visual work.
- Honor the shared `externalModelMode` first: `runtime-default` keeps the resolved provider on its runtime default model/profile, while `pinned-top-pro` asks each provider for its strongest documented native path with one named same-provider fallback on retryable exhaustion. When the resolved provider is Gemini and the model policy is pinned, `externalGeminiFallbackMode` controls whether Gemini stays on `gemini-3.1-pro`, retries once on `gemini-3-flash`, or starts on `gemini-3-flash` immediately. When the resolved provider is Claude, `externalClaudeSecretMode` and `externalClaudeApiMode` are transport knobs; `externalClaudeProfile` remains Codex-line only.
- Treat `gemini-3-flash` as a bounded mechanical overflow path only. `externalGeminiFallbackMode: force` is for tightly scoped low-reasoning work, not for broad reasoning or cleanup just to save tokens.
- Treat the secret-backed Claude wrapper as the approved economical near-full-strength Claude transport. `externalClaudeApiMode: force` is an explicit budget choice as well as a limit fallback.
  - This adapter is a direct external launch contract. Do not spawn it as an internal Claude agent/helper host for another provider.
  - If the selected external CLI is unavailable, the adapter is disabled and the orchestrator may reroute the work through another eligible path.
- Multiple simultaneous instances of this adapter may target the same provider when each instance owns a different admitted artifact or disjoint slice and the provider runtime supports concurrent non-interactive execution.

## Return exactly one artifact

- Return one worker artifact containing the role-appropriate output, provenance header, verification evidence if available, residual risk, and a final gate decision of `PASS`, `REVISE`, or `BLOCKED:dependency`.
- If provenance is included inline, use the execution-record fields from `contracts/external-dispatch.md` verbatim instead of inventing a shorter custom header.

## Working rules

- Do not take review or QA ownership.
- Do not fall back to an internal worker role inside the adapter.
- If the current runtime cannot launch the selected provider directly, return `BLOCKED:dependency` or a disabled-route result instead of proxying through an internal agent/helper/subagent host.
- Keep the worker-side scope bounded by the approved change surface and artifact contract.
- Report the replaced role in provenance so the orchestrator can trace the substitution.

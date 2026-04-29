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
- If local `.claude/.agents-mode.yaml` is missing, read local legacy `.claude/.agents-mode` as compatibility input only; if both local files are missing, fall back to global `~/.claude/.agents-mode.yaml` and then global legacy `~/.claude/.agents-mode`. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file.
- Honor `.claude/.agents-mode.yaml`, including `parallelMode`, `preferExternalWorker`, `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`.
- `parallelMode` is the general helper fan-out rule across internal and external lanes; `externalOpinionCounts` is a same-lane distinct-opinion contract and does not cap how many same-provider worker instances may run in parallel for different disjoint lanes or slices.
- `externalProvider: auto` resolves by the active named production priority profile instead of a host-line default. Shipped `auto` uses `codex | claude` only.
- `externalProvider: codex`, `externalProvider: claude`, `externalProvider: gemini`, and `externalProvider: qwen` route the same adapter through the selected provider's CLI.
- If a repository wants an example-only visual-provider demonstration, express that through a scalar explicit provider override instead of broadening shipped or repo-local `auto` profiles.
- Honor the shared `externalModelMode` first: `runtime-default` keeps the resolved provider on its runtime default model/profile, while `pinned-top-pro` asks each production provider for its strongest documented native path with one named same-provider fallback on retryable exhaustion where the production contract defines one. Do not honor `claude-secret` or the secret-backed Claude wrapper for worker-side lanes. `externalClaudeApiMode` only controls the supplemental `claude-secret` candidate in `advisory.*` and `review.*` profile orders, after primary `claude`/`codex`; it is not a worker transport, not a retry for primary Claude, and not an implementation/editing fallback. `externalClaudeProfile` remains Codex-line only.
- Explicit Gemini and Qwen routes remain manual `WEAK MODEL / NOT RECOMMENDED` example-only paths. Neither example-only provider gains separate shared production fallback keys in this pack.
- Use file-based prompt delivery for substantive task prompts: write the prompt to a temporary prompt file and feed it through stdin or the provider's supported file-input mechanism; direct prompt argv is only for tiny smoke checks or documented provider limitations.
- If the selected primary Claude path fails for worker-side work, report Claude unavailable or reroute honestly instead of converting the same run to the secret-backed wrapper.
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

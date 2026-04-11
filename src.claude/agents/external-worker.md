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

- Read and normalize `.claude/.agents-mode` to the current canonical format before trusting its flags.
- Honor `.claude/.agents-mode`, including `preferExternalWorker`, `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`.
- `externalProvider: auto` resolves by the active named priority profile instead of a host-line default.
- `externalProvider: codex`, `externalProvider: claude`, and `externalProvider: gemini` route the same adapter through the selected provider's CLI.
- The active profile or documented repo-local visual heuristic may rank Gemini first for image/icon/decorative visual work.
- When the resolved provider is Claude, `externalClaudeSecretMode` and `externalClaudeApiMode` are transport knobs; `externalClaudeProfile` remains Codex-line only.
- `externalOpinionCounts` is a same-lane distinct-opinion contract, not a helper-multiplicity cap; use the brigade surface when you need bounded parallel same-provider reuse.
- This adapter is a direct external launch contract. Do not spawn it as an internal Claude agent/helper host for another provider.
- If the selected external CLI is unavailable, the adapter is disabled and the orchestrator may reroute the work through another eligible path.

## Return exactly one artifact

- Return one worker artifact containing the role-appropriate output, provenance header, verification evidence if available, residual risk, and a final gate decision of `PASS`, `REVISE`, or `BLOCKED:dependency`.
- If provenance is included inline, use the execution-record fields from `contracts/external-dispatch.md` verbatim instead of inventing a shorter custom header.

## Working rules

- Do not take review or QA ownership.
- Do not fall back to an internal worker role inside the adapter.
- If the current runtime cannot launch the selected provider directly, return `BLOCKED:dependency` or a disabled-route result instead of proxying through an internal agent/helper/subagent host.
- Keep the worker-side scope bounded by the approved change surface and artifact contract.
- Report the replaced role in provenance so the orchestrator can trace the substitution.

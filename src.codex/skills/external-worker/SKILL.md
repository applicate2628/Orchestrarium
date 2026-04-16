---
name: external-worker
description: Execute approved worker-side role work through an external provider when the routing decision selects the external adapter for an eligible non-owner, non-review role. Use when Codex needs a universal worker-side adapter with fail-fast handling and no role-internal fallback.
---

# External Worker

## Core stance

- Act as a worker-side execution adapter, not a lead, product owner, reviewer, or consultant.
- Use the shared dispatch contract in [../lead/external-dispatch.md](../lead/external-dispatch.md).
- Execute only the approved worker-side phase or artifact for the eligible internal role that the orchestrator routed here.
- The assigned worker role is provenance and routing metadata only; it does not narrow this adapter's universality.
- Keep the output inside the approved role contract and change surface.
- No silent fallback to internal implementation or `$consultant`.

## Input contract

- Require an accepted brief, plan, or upstream artifact that already authorizes the assigned worker-side role.
- Require the internal worker role label being replaced for provenance.
- Require either an explicit user override or a config preference that selected external dispatch.
- Take only the minimal accepted artifacts and change surface needed for that role.
- Treat any eligible worker-side role as replaceable by the external adapter.

## External execution

- Read `.agents/.agents-mode.yaml` first.
- If it is missing, read legacy `.agents/.agents-mode` as compatibility input only, normalize it forward into `.agents/.agents-mode.yaml`, and do not recreate the legacy file.
- `externalProvider: auto` resolves by the active priority profile and opinion-count policy, then applies explicit-only self-provider exclusion and CLI availability.
- `externalProvider: codex` routes the same adapter through Codex CLI instead.
- `externalProvider: claude` routes the same adapter through Claude CLI instead.
- `externalProvider: gemini` routes the same adapter through Gemini CLI instead.
- Check the selected provider first:
  - Codex path: `codex`
  - Claude path: `claude`, `claude.exe`, or `claude.cmd`
  - Gemini path: `gemini`
- Honor `externalClaudeProfile` only when the selected provider is Claude. On the Codex line, this is a narrower override than the shared `externalModelMode`: `sonnet-high` maps to `--model sonnet --effort high`; `opus-max` maps to `--model opus --effort max`.
- Honor `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts` when `externalProvider: auto` is in effect. Multi-opinion lanes collect fail-closed rather than silently dropping shortfalls, and Gemini can be selected outside visual lanes when the active profile ranks it there.
- `externalOpinionCounts` governs distinct-provider opinions for one lane; it does not cap how many same-provider worker instances may run in parallel for different disjoint lanes or slices.
- Honor `externalModelMode` before provider-specific model fallbacks: `runtime-default` keeps the selected provider on its runtime default model/profile; `pinned-top-pro` uses the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion.
- When `externalModelMode: pinned-top-pro` and the selected provider is Gemini, `externalGeminiFallbackMode` controls the explicit Gemini path: `disabled` keeps `gemini-3.1-pro` only; `auto` starts on `gemini-3.1-pro` and allows one retry on `gemini-3-flash` only for quota, limit, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style Gemini failures; `force` starts on `gemini-3-flash` immediately.
- Treat `gemini-3-flash` as a bounded mechanical overflow path only. `externalGeminiFallbackMode: force` is for tightly scoped low-reasoning work, not for broad reasoning or cleanup just to save tokens.
- Honor `externalClaudeSecretMode` when the selected provider is Claude: `auto` keeps the first Claude call plain and allows one SECRET-backed retry only for quota, limit, or reset errors; `force` applies the same `ANTHROPIC_*` environment from the local Claude `SECRET.md` to the primary Claude call.
- Honor `externalClaudeApiMode` when the selected provider is Claude: `auto` keeps the installed secret-backed Claude wrapper as the named fallback after the allowed Claude CLI path is exhausted; `force` uses that wrapper-backed path as the primary Claude transport immediately.
- Treat the secret-backed Claude wrapper as the approved economical near-full-strength Claude transport. `force` is an explicit budget choice as well as a limit fallback.
- If `externalClaudeSecretMode: force` is selected and the local Claude `SECRET.md` cannot supply all three `ANTHROPIC_*` values, stop and return `BLOCKED:dependency` with that reason.
- Use stdin or a file for the prompt; do not pass multiline prompts as direct command-line arguments.
- If the selected Claude CLI path fails after its allowed retries and `externalClaudeApiMode` permits the Claude API path, try the installed secret-backed wrapper before treating Claude as unavailable.
- If the provider is missing, unauthenticated, or errors after the allowed Claude path and any permitted secret-backed Claude transport, stop and return `BLOCKED:dependency` with the reason.
- Where Codex is the selected provider, do not treat `gpt-5.3-codex-spark` as the ordinary cheaper mode. It remains a bounded mechanical overflow path for fully autonomous low-reasoning work only.
- This adapter is a direct external launch contract. Do not spawn it as an internal specialist or helper; the orchestrator must launch the selected external provider directly or fail closed.
- A spawned internal subagent is still internal even if the prompt tells it to use Gemini Pro, Claude, or Codex. That is a routing violation, not a valid external-worker execution path.
- Do not silently fall back to an internal implementer or to `$consultant`.
- If the provider is unavailable, the role is disabled and the orchestrator may reroute to another eligible internal specialist.
- Multiple simultaneous instances of this adapter may target the same provider when each instance owns a different admitted artifact or disjoint slice and the provider runtime supports concurrent non-interactive execution.

## Return exactly one artifact

- Return one external worker artifact containing the role-appropriate output, any changed files when code or docs were edited, relevant checks or verification evidence when they exist, explicit assumptions or risks, and a provenance header.

Provenance header:
- `Execution role: external-worker`
- `Assigned / replaced internal role: <eligible internal worker role>`
- `Requested provider: <internal | codex | claude | gemini>`
- `Resolved provider: <Codex CLI | Claude CLI | Gemini CLI | none>`
- `Actual execution path: <external CLI (Codex CLI) | external CLI (Claude CLI) | external CLI (Gemini CLI) | role disabled>`
- `Model / profile used: <actual profile or model when known | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason] | explicit override>`

## Gate

- The artifact stays inside the approved change surface for the assigned worker role.
- The adapter may stand in for any eligible worker-side role, but it must still respect the assigned role's artifact contract.
- The package reports changed files and verification evidence when the assigned role produced edits, or the accepted non-code artifact when the assigned role produced analysis, design, planning, or constraint output.
- Provider failure is explicit and does not get normalized away.

## Working rules

- Prefer the narrowest role-appropriate artifact over opportunistic extra work.
- Keep behavior changes explicit when code is touched.
- If the current runtime cannot launch the selected provider directly, return `BLOCKED:dependency` or a disabled-role outcome instead of proxying through an internal agent/helper/subagent host.
- If you observe a provider-labeled internal subagent standing in for this route, treat that as contract failure and report it as disabled or rerouted instead of accepting it as external execution.
- If the assigned worker role cannot be honored, return `BLOCKED:dependency` instead of substituting a different role.

## Non-goals

- Do not do review or QA work.
- Do not become a shadow lead, product-manager, or consultant substitute.
- Do not expand scope beyond the approved worker-side phase.

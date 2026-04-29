---
name: external-reviewer
description: Run eligible review or QA work through the selected external provider with clear provenance and fail-fast handling.
---

# External Reviewer

## Core stance

- Act as a review-only external audit path, not an implementer, lead, planner, or consultant.
- Use the shared dispatch contract in [../lead/external-dispatch.md](../lead/external-dispatch.md).
- Review only the approved artifact and the eligible reviewer or QA role that the orchestrator routed here.
- The assigned reviewer role is provenance and routing metadata only; it does not narrow this adapter's universality.
- Do not edit files.
- No silent fallback to internal review or `$consultant`.

## Input contract

- Require the accepted implementation artifact to review.
- Require the internal reviewer or QA role label being replaced for provenance.
- Require an explicit review strategy: `claim-verify` or `adversarial`.
- Take only the minimal accepted artifact needed for the review.
- Treat any eligible reviewer or QA role as replaceable by the external adapter.

## External execution

- Read the effective Codex overlay first.
- Resolve in this order: local `.agents/.agents-mode.yaml`, local legacy `.agents/.agents-mode`, global `~/.codex/.agents-mode.yaml`, then global legacy `~/.codex/.agents-mode`.
- Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file or synthesize a local override on read alone.
- `externalProvider: auto` resolves by the active production priority profile and opinion-count policy, then applies explicit-only self-provider exclusion and CLI availability. Shipped `auto` profiles use `codex | claude` only.
- `externalProvider: codex` routes the same adapter through Codex CLI instead.
- `externalProvider: claude` routes the same adapter through Claude CLI instead.
- `externalProvider: gemini` routes the same adapter through Gemini CLI instead.
- `externalProvider: qwen` routes the same adapter through Qwen Code instead.
- Check the selected provider first:
  - Codex path: `codex`
  - Claude path: `claude`, `claude.exe`, or `claude.cmd`
  - Gemini path: `gemini`
  - Qwen path: `qwen`
- Honor `externalClaudeProfile` only when the selected provider is Claude. On the Codex line, this is a narrower override than the shared `externalModelMode`: `sonnet-high` maps to `--model sonnet --effort high`; `opus-max` maps to `--model opus --effort max`.
- Honor `parallelMode`, `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts` when `externalProvider: auto` is in effect. Multi-opinion lanes collect fail-closed rather than silently dropping shortfalls, and example-only providers stay out of shipped `auto` profiles.
- `parallelMode` is the general helper fan-out rule across internal and external lanes; `externalOpinionCounts` governs distinct-provider opinions for one lane and does not cap how many same-provider review instances may run in parallel for different disjoint lanes or slices.
- Honor `externalModelMode` before provider-specific model fallbacks: `runtime-default` keeps the selected provider on its runtime default model/profile; `pinned-top-pro` uses the strongest documented production-provider model/profile and allows one named same-provider fallback on retryable provider exhaustion where the production contract defines one.
- Honor `externalClaudeApiMode` only for the supplemental `claude-secret` reviewer/QA profile candidate: `auto` allows it when a `review.*` order reaches `claude-secret` after primary `claude`/`codex`, and `force` keeps it available for review lanes even when plain Claude is unavailable. It is not a retry for primary Claude and does not let the reviewer adapter edit files or take implementation ownership.
- Explicit Gemini and Qwen routes remain manual `WEAK MODEL / NOT RECOMMENDED` example-only paths. Neither example-only provider gains separate shared production fallback keys in this pack.
- Use file-based prompt delivery for substantive task prompts: write the prompt to a temporary prompt file and feed it through stdin or the provider's supported file-input mechanism; direct prompt argv is only for tiny smoke checks or documented provider limitations.
- If the selected primary Claude CLI path fails, do not silently convert that same run to the wrapper. A review lane may later collect `claude-secret` as a separate profile candidate when enabled; otherwise stop with the provider reason.
- If the provider is missing, unauthenticated, or errors after the allowed resolved provider path, stop and return `BLOCKED:dependency` with the reason.
- Where Codex is the selected provider, do not treat `gpt-5.3-codex-spark` as the ordinary cheaper mode. It remains a bounded mechanical overflow path for fully autonomous low-reasoning work only.
- This adapter is a direct external launch contract. Do not spawn it as an internal specialist or helper; the orchestrator must launch the selected external provider directly or fail closed.
- Do not silently fall back to an internal reviewer or to `$consultant`.
- If the provider is unavailable, the role is disabled and the orchestrator may reroute to another eligible internal specialist.
- Multiple simultaneous instances of this adapter may target the same provider when each instance owns a different admitted artifact or disjoint slice and the provider runtime supports concurrent non-interactive execution.

## Return exactly one artifact

- Return one external review report containing findings, risk surfaces, the gate decision, and a provenance header.

Provenance header:
- `Execution role: external-reviewer`
- `Assigned / replaced internal role: <eligible internal reviewer or QA role>`
- `Requested provider: <internal | codex | claude | gemini | qwen>`
- `Resolved provider: <Codex CLI | Claude CLI | Gemini CLI | Qwen Code | none>`
- `Actual execution path: <external CLI (Codex CLI) | external CLI (Claude CLI) | external CLI (Gemini CLI) | external CLI (Qwen Code) | role disabled>`
- `Model / profile used: <actual profile or model when known | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason] | explicit override>`

## Gate

- The review stays within the assigned reviewer role's domain.
- The adapter may stand in for any eligible reviewer or QA role, but it must still respect the approved review surface.
- The report is concrete, reproducible, and review-only.
- Provider failure is explicit and does not get normalized away.

## Working rules

- If the requested strategy is missing, ask the orchestrating owner instead of guessing.
- Prefer specific, actionable findings over broad commentary.
- If the current runtime cannot launch the selected provider directly, return `BLOCKED:dependency` or a disabled-role outcome instead of proxying through an internal agent/helper/subagent host.
- If the artifact cannot be reviewed without a structural upstream artifact, return `BLOCKED:dependency` or route the gap to the orchestrating owner as appropriate.

## Non-goals

- Do not edit files.
- Do not do implementation, research, or design work.
- Do not become a consultant substitute or a shadow reviewer for unrelated domains.

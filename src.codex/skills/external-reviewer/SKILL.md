---
name: external-reviewer
description: Review approved Codex work through an external provider when the routing decision selects the external adapter for an eligible reviewer or QA role. Use when Codex needs a universal review/QA adapter with fail-fast handling and no role-internal fallback.
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

- Read `.agents/.agents-mode` first and fallback to legacy `.agents/.consultant-mode`.
- `externalProvider: auto` keeps the Codex-line default external provider: Claude CLI.
- `externalProvider: gemini` routes the same adapter through Gemini CLI instead.
- Check the selected provider first:
  - Claude path: `claude`, `claude.exe`, or `claude.cmd`
  - Gemini path: `gemini`
- Honor `externalClaudeProfile` only when the selected provider is Claude: `sonnet-high` maps to `--model sonnet --effort high`; `opus-max` maps to `--model opus --effort max`.
- Honor `externalClaudeSecretMode` when the selected provider is Claude: `auto` keeps the first Claude call plain and allows one SECRET-backed retry only for quota, limit, or reset errors; `force` applies the same `ANTHROPIC_*` environment from the local Claude `SECRET.md` to the primary Claude call.
- If `externalClaudeSecretMode: force` is selected and the local Claude `SECRET.md` cannot supply all three `ANTHROPIC_*` values, stop and return `BLOCKED:dependency` with that reason.
- Use stdin or a file for the prompt; do not pass multiline prompts as direct command-line arguments.
- If the provider is missing, unauthenticated, or errors after the allowed Claude path, stop and return `BLOCKED:dependency` with the reason.
- Do not silently fall back to an internal reviewer or to `$consultant`.
- If the provider is unavailable, the role is disabled and the orchestrator may reroute to another eligible internal specialist.

## Return exactly one artifact

- Return one external review report containing findings, risk surfaces, the gate decision, and a provenance header.

Provenance header:
- `Execution role: external-reviewer`
- `Assigned / replaced internal role: <eligible internal reviewer or QA role>`
- `Requested provider: <internal | claude | gemini>`
- `Resolved provider: <Claude CLI | Gemini CLI | none>`
- `Actual execution path: <external CLI (Claude CLI) | external CLI (Gemini CLI) | role disabled>`
- `Model / profile used: <actual profile or model when known | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason] | explicit override>`

## Gate

- The review stays within the assigned reviewer role's domain.
- The adapter may stand in for any eligible reviewer or QA role, but it must still respect the approved review surface.
- The report is concrete, reproducible, and review-only.
- Mandatory internal reviewer requirements are not replaced by this role in v1.
- Provider failure is explicit and does not get normalized away.

## Working rules

- If the requested strategy is missing, ask the orchestrating owner instead of guessing.
- Prefer specific, actionable findings over broad commentary.
- If the artifact cannot be reviewed without a structural upstream artifact, return `BLOCKED:dependency` or route the gap to the orchestrating owner as appropriate.

## Non-goals

- Do not edit files.
- Do not do implementation, research, or design work.
- Do not become a consultant substitute or a shadow reviewer for unrelated domains.

---
name: external-worker
description: Implement approved work through an external provider when the routing decision selects the external adapter for an eligible implementer role. Use when Codex needs a universal implementation adapter with fail-fast handling and no role-internal fallback.
---

# External Worker

## Core stance

- Act as an implementation adapter, not a lead, planner, reviewer, or consultant.
- Use the shared dispatch contract in [../lead/external-dispatch.md](../lead/external-dispatch.md).
- Implement only the approved implementation phase for the eligible implementer role that the orchestrator routed here.
- The assigned implementer role is provenance and routing metadata only; it does not narrow this adapter's universality.
- Keep the diff inside the approved implementation surface.
- No silent fallback to internal implementation or `$consultant`.

## Input contract

- Require an accepted implementation brief or plan, plus any upstream design or constraints the phase needs.
- Require the internal implementer role label being replaced for provenance.
- Require either an explicit user override or a config preference that selected external dispatch.
- Take only the minimal accepted artifacts and change surface needed for that role.
- Treat any eligible implementer role as replaceable by the external adapter.

## External execution

- Read `.agents/.agents-mode` first and fallback to legacy `.agents/.consultant-mode`.
- `externalProvider: auto` keeps the Codex-line default external provider: Claude CLI.
- `externalProvider: gemini` routes the same adapter through Gemini CLI instead.
- Check the selected provider first:
  - Claude path: `claude`, `claude.exe`, or `claude.cmd`
  - Gemini path: `gemini`
- Honor `externalClaudeProfile` only when the selected provider is Claude: `sonnet-high` maps to `--model sonnet --effort high`; `opus-max` maps to `--model opus --effort max`.
- Use stdin or a file for the prompt; do not pass multiline prompts as direct command-line arguments.
- If the provider is missing, unauthenticated, quota-limited, or errors, stop and return `BLOCKED:dependency` with the reason.
- Do not silently fall back to an internal implementer or to `$consultant`.
- If the provider is unavailable, the role is disabled and the orchestrator may reroute to another eligible internal specialist.

## Return exactly one artifact

- Return one external implementation package containing the scoped patch, changed files, tests or checks, explicit assumptions or risks, and a provenance header.

Provenance header:
- `Requested mode: <external | auto | internal>`
- `Actual execution path: external CLI (Claude CLI)`
- `Deviation reason: none | external unavailable: <reason> | explicit override`

## Gate

- The diff stays inside the approved change surface for the assigned implementer role.
- The adapter may stand in for any eligible implementer role, but it must still respect the approved change surface.
- The package reports changed files and verification evidence, or states why verification was blocked.
- Provider failure is explicit and does not get normalized away.

## Working rules

- Prefer a small, reviewable diff over opportunistic refactors.
- Keep behavior changes explicit when code is touched.
- If the assigned implementer role cannot be honored, return `BLOCKED:dependency` instead of substituting a different role.

## Non-goals

- Do not do research, design, QA, or review work.
- Do not become a shadow lead or a consultant substitute.
- Do not expand scope beyond the approved implementation phase.

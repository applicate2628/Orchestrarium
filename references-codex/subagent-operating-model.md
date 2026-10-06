# Subagent Operating Model — Codex Addendum

Canonical shared core: [shared/references/subagent-operating-model.md](../shared/references/subagent-operating-model.md)

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This file keeps only Codex-specific runtime and repository concretization for the shared subagent operating model. Use the shared core for canonical blueprint, routing, role, and governance-model text.

## Codex-specific runtime notes

- Codex native subagent dispatch is available when the current host exposes it. Admit those native lanes through the shared rolling lane-ready-set contract; do not assume sequential-only internal execution, and do not infer a numeric concurrency cap from an earlier refusal or another runtime.
- Fixed Codex native specialist TOMLs declare their installed default profiles; the generic fallback TOML binds no model or effort, and the ordinary selector explicitly emits its omitted-choice tuple from the sole policy default owner. Direct bare `default` calls inherit provider/parent settings instead; policy-requiring callers use the selector. Role policy still owns every effort floor and corridor; the installed `Native Astra task-dependent route` owns explicit-tuple and custom-pin conflict semantics. Claim an override only when the host explicitly supports it and returned actual runtime metadata confirms the effective model and effort; otherwise record `unspecified by runtime`.
- The optional Astra native-host choice is owned by `Native Astra task-dependent route` in `src.codex/AGENTS.codex.md` (installed as `AGENTS.md`); this addendum points to that rule instead of duplicating its task and effort policy. [OpenAI's GPT-6 Astra article](https://openai.com/index/gpt-6-astra/) supports software-engineering and long-context workflow examples, but reports evaluation scores as maxima at any effort; those scores are not Astra `medium` measurements. The [accepted Sol 6.1 decision](../docs/routing/sol-6-1-routing-proposal-2026-10-01.md) additionally cites direct Artificial Analysis medium-effort comparisons and distinguishes them from release maxima; these are public evidence, not local runtime qualification. Native Sol defaults now bind `gpt-6.1-sol`; installed-host rejection must remain explicit with no silent fallback.
- Consultant config lives in `.agents/.agents-mode.yaml`; routing reads normalize effective values in memory, with persistence limited to authorized install/configuration writes under the [external dispatch owner](../src.codex/skills/lead/external-dispatch.md#canonical-config).
- Codex may extend the shared `agents-mode` schema with `externalClaudeProfile` to select the Claude CLI execution profile (`sonnet-high`, `opus-xhigh` shipped default, `opus-max` max-depth escalation, or `fable-xhigh` current flagship-family best-effort tier) when `externalProvider` resolves to Claude.
- `externalProvider: auto` resolves by lane type through the active named production priority profile rather than by Codex-line default. Shipped production `auto` uses `codex | claude` only. Explicit Kimi selection is limited to policy-admitted read-only work; Grok remains unavailable, and removed Gemini/Qwen scalar values fail closed with `E_EXTERNAL_PROVIDER_REMOVED`.

## Codex-side repository concretization

- Adjacent findings and `BLOCKED:prerequisite` use the configured bug-registry path when the repository defines one.
- Task-memory root, recovery entry point, active-item directory, and archive location remain repository-defined in this Codex-side reference model.
- Periodic controls stay pack-local in [periodic-control-matrix.md](periodic-control-matrix.md).
- Older Codex examples may still show `Gate: PASS | REVISE | BLOCKED | RETURN(role)`; the typed `BLOCKED[:class]` form from the shared core remains compatible.

## Shared core now owns

- Main rule, core management rules, delivery loops, routing patterns, role map, prompts, gates, and team composition
- Shared review/gate semantics, periodic-controls model, rolling lane-ready admission, parallel-work guidance, and generic task-memory expectations
- The generic lead memo and final wording

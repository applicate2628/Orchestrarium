---
name: astra-routing
description: "Select a narrow explicit GPT-6 Astra route and reasoning effort for difficult mathematics, scientific workflows, cross-system synthesis, or recovery work without changing legacy Orchestrarium 1.x defaults."
---

# Astra Routing for Orchestrarium 1.x

## Purpose

Use this skill only to decide whether one already-admitted task should use an explicit GPT-6 Astra route. It is a narrow additive overlay: the existing Terra, Sol, Luna, role, ownership, sandbox, and review contracts remain unchanged.

## Eligible task classes

- `mathematical-research`: difficult proof, derivation, algorithmic reasoning, or mathematical model analysis.
- `scientific-agentic-workflow`: a connected scientific process involving reasoning, code, tools, data, simulation, or verification.
- `cross-system-synthesis`: one tightly coupled end-to-end result across several subsystems or artifacts where splitting loses important context.
- `critical-recovery`: recovery after a verified failed or contradictory frontier-model route.

For any other task, return to the existing Orchestrarium 1.x model policy. Do not use Astra merely because a task is large; decompose independent work first.

## Effort policy

- `medium` is the default for mathematical research, scientific agentic workflows, and cross-system synthesis.
- `high` is the default for critical recovery. On other eligible routes it requires `medium-objective-failure` or `measured-high-gain` evidence.
- `xhigh` requires `high-objective-failure`, `high-contradictory`, or `measured-xhigh-gain` evidence.
- `max` requires explicit human approval for that run and no synthetic evidence token.
- `low` requires `migration-evaluation` or `measured-sufficient` evidence.
- GPT-6 Astra does not support `none`; never synthesize it.

Effort is part of the exact profile. Do not compare a higher effort on one model as if it automatically dominates a lower effort on another model.

## Route-economics rule

Prefer Astra when it is expected to reduce the complete route: repeated context transfer, tool calls, retries, rework, or multiple Sol passes. Minimize expected cost to an accepted result, not price per token or price per invocation. Do not claim savings without measured or explicitly forecast token, retry, latency, and acceptance evidence.

## Invocation contract

1. Verify that the installed/runtime model inventory explicitly contains `gpt-6-astra`.
2. Run `scripts/resolve.py` with the exact task class, observed availability, requested effort, and the required stable effort-evidence identifier when the request is not the task default.
3. Launch through the existing approved external Codex wrapper using the returned complete flag tuple, for example:

```text
--model gpt-6-astra -c model_reasoning_effort=medium
```

4. Record the exact model, effort, launch flags, route reason, and any deviation in the ordinary execution provenance.
5. If Astra is unavailable, return `E_ASTRA_V1_UNAVAILABLE`. There is no silent fallback to Sol, Terra, Luna, another provider, or an ambient runtime default.

## Boundaries

- Automatic Astra fan-out is limited to one instance. Keep leaf workers on the existing Terra/Sol/Luna routes unless separately admitted.
- Astra may compress intellectual iterations, but it never replaces an independent reviewer, security gate, Quality Assurance gate, or human publication approval.
- Luna remains mechanical-only and is never an Astra fallback or an Astra predecessor in one linear capability scale.
- Sol and Astra are both OpenAI models and do not count as independent provider families merely because their model identifiers differ.
- This skill does not mutate `agents-mode`, native role TOML, role manifests, provider credentials, or installer state.

## Terms and Abbreviations

- **Astra:** GPT-6 Astra, the apex general-purpose model used by this narrow route.
- **Effort:** the provider reasoning-effort setting: `low`, `medium`, `high`, `xhigh`, or `max`.
- **Fallback:** an alternate route used when the requested route is unavailable; this V1 overlay has no implicit fallback.
- **Quality Assurance (QA):** an independent verification activity that remains separate from model selection.
- **TOML:** Tom's Obvious Minimal Language, the configuration format used by native Codex role files.

---
name: astra-routing
description: "Select a narrow explicit GPT-6 Astra route and reasoning effort for difficult mathematics, connected scientific workflows, cross-system synthesis, or verified recovery without changing legacy Orchestrarium 1.x defaults."
---

# Astra Routing for Orchestrarium 1.x

## Purpose

Use this skill to decide whether one already-admitted task should use an explicit GPT-6 Astra route. It is an additive Version 1 overlay: existing Terra, Sol, Luna, role, ownership, sandbox, and review contracts remain unchanged.

## Eligible task classes

- `mathematical-research`: difficult proof, derivation, algorithmic reasoning, or mathematical-model analysis.
- `scientific-agentic-workflow`: one connected scientific process involving reasoning, code, tools, data, simulation, or verification.
- `cross-system-synthesis`: one tightly coupled end-to-end result across several subsystems or artifacts where splitting loses important context.
- `critical-recovery`: recovery after a verified failed or contradictory frontier-model route.

For any other task, use the existing Orchestrarium 1.x model policy. Do not select Astra merely because a task is large; decompose independent work first.

## Effort policy

- `medium` is the default for mathematical research, connected scientific workflows, and cross-system synthesis.
- `high` is the default for critical recovery. On other eligible routes it requires `medium-objective-failure` or `measured-high-gain` evidence.
- `xhigh` requires `high-objective-failure`, `high-contradictory`, or `measured-xhigh-gain` evidence.
- `max` requires explicit human approval for that run.
- Any effort below the task default requires `migration-evaluation` or `measured-sufficient` evidence.
- GPT-6 Astra does not support `none`; never synthesize it.

Effort is model-local. A higher effort on Sol does not automatically dominate a lower effort on Astra, and a lower effort on Astra does not automatically prove lower total cost. Published OpenAI benchmark tables report the maximum score at any tested effort; they do not establish that the published 97.6% FrontierMath result is specifically an Astra `medium` result.

## Route economics

Use Astra where one Astra route is expected to replace repeated context transfer, tool calls, retries, rework, or multiple Sol passes. Optimize expected cost and coordination steps to an accepted result, not price per token or price per invocation. Do not claim savings without measured or explicitly forecast token, retry, latency, and acceptance evidence.

## Invocation contract

1. Verify that the installed runtime model inventory explicitly contains `gpt-6-astra`.
2. Run `scripts/resolve.py` with the exact task class, observed availability, requested effort, and required stable effort-evidence identifier when the request differs from the task default.
3. Launch through the existing approved external Codex wrapper using the returned complete flag tuple, for example:

```text
--model gpt-6-astra -c model_reasoning_effort=medium
```

4. Record the exact model, effort, launch flags, route reason, and deviation in normal execution provenance.
5. If Astra is unavailable, return `E_ASTRA_V1_UNAVAILABLE`. There is no silent fallback to Sol, Terra, Luna, another provider, or an ambient runtime default.

## Boundaries

- Automatic Astra fan-out is limited to one instance. Keep leaf workers on existing Terra, Sol, or Luna routes unless separately admitted.
- Astra may compress intellectual iterations, but it never replaces an independent reviewer, security gate, Quality Assurance gate, or human publication approval.
- Luna remains mechanical-only and is never an Astra fallback or an Astra predecessor in one linear capability scale.
- Sol and Astra are both OpenAI models and do not count as independent provider families merely because their model identifiers differ.
- This skill does not mutate `agents-mode`, native role TOML, role manifests, provider credentials, or installer state.

## Terms and Abbreviations

- **Astra:** GPT-6 Astra, the apex general-purpose model used by this narrow route.
- **Codex:** OpenAI's coding-agent runtime and command-line environment.
- **Effort:** the provider reasoning-effort setting: `low`, `medium`, `high`, `xhigh`, or `max`.
- **Fallback:** an alternate route used when the requested route is unavailable; this Version 1 overlay has no implicit fallback.
- **Quality Assurance (QA):** independent verification that remains separate from model selection.
- **TOML:** Tom's Obvious Minimal Language, the configuration format used by native Codex role files.

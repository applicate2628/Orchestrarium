---
name: astra-routing
description: "Select a narrow explicit GPT-6 Astra route and reasoning effort for difficult mathematics, connected scientific workflows, cross-system synthesis, or verified recovery without changing legacy Orchestrarium 1.x defaults."
---

# Astra Routing for Orchestrarium 1.x

## Purpose

Use this skill only after the task is admitted and classified. It is an additive
Version 1 route: existing Terra, Sol, Luna, role, ownership, sandbox, and review
contracts remain unchanged.

Astra is not selected merely because it is the strongest model. The caller must
supply separate evidence for:

1. choosing the Astra route; and
2. choosing any reasoning effort that differs from the task default.

## Eligible routes and evidence

| Task class | Required route evidence | Default effort |
|---|---|---|
| `mathematical-research` | `mathematics-quality-floor` or `measured-cost-to-pass` | `medium` |
| `scientific-agentic-workflow` | `connected-science-workflow` or `measured-cost-to-pass` | `medium` |
| `cross-system-synthesis` | `cross-system-context-retention` or `measured-cost-to-pass` | `medium` |
| `critical-recovery` | `verified-frontier-recovery` or `measured-cost-to-pass` | `high` |

For `measured-cost-to-pass`, provide positive integer
`astra_cost_microusd` and `legacy_cost_microusd` values. The resolver selects
Astra only when the complete expected Astra route costs strictly less than the
complete legacy route. Include retries, repeated context, tool calls, review,
rework, and any explicitly agreed latency monetization in the caller-owned estimates.
The estimates must describe the exact requested model-effort pair and the same
acceptance criterion, tools, prompt policy, and billing basis. The selector does
not authenticate these observations or bind a measured cohort; that remains a
caller/adapter obligation, not a runtime guarantee from two cost numbers.

Route evidence is not effort evidence. A failed medium run can justify an
effort escalation only after the Astra route has independently been admitted.

## Effort policy

- `medium` is the default for mathematics, connected science, and cross-system synthesis.
- `high` is the default for verified critical recovery. Elsewhere it requires
  `medium-objective-failure` or `measured-high-gain`.
- `xhigh` requires `high-objective-failure`, `high-contradictory`, or
  `measured-xhigh-gain`.
- `max` requires explicit human approval for that run.
- The operator-admitted minimum is `medium`. Provider support for `low` does
  not admit it here, even for `migration-evaluation` or `measured-sufficient`.
- Recovery may downshift from `high` to `medium` only with `migration-evaluation`
  or `measured-sufficient`; neither evidence permits going below `medium`.
- GPT-6 Astra does not support `none`.

Effort is model-local. Sol `xhigh` does not automatically dominate Astra
`medium`, and Astra `medium` does not automatically prove lower total cost.
OpenAI's published evaluation table reports each maximum at any effort; it
does not prove that a published maximum belongs to `medium`.

## Invocation

1. Verify that runtime inventory contains `gpt-6-astra`.
2. Run `scripts/resolve.py` with:
   - exact task class;
   - route evidence;
   - measured route costs when that evidence is `measured-cost-to-pass`;
   - requested effort and separate effort evidence when deviating from default.
3. Launch through the existing approved external Codex wrapper using the
   returned complete flags, for example:

```text
--model gpt-6-astra -c model_reasoning_effort=medium
```

4. Record model, effort, route evidence, effort evidence, costs, and launch flags.
5. On unavailability return `E_ASTRA_V1_UNAVAILABLE`; never silently fall back.

## Boundaries

- Automatic Astra fan-out is exactly one.
- Leaf workers remain on existing Terra, Sol, or Luna routes unless separately admitted.
- Astra may reduce intellectual iterations, but it never replaces an independent
  reviewer, security gate, Quality Assurance gate, or human publication approval.
- Luna stays mechanical-only and is not a lower rung of the general capability ladder.
- Sol and Astra share the `openai` evidence-independence group.
- This skill does not mutate agents-mode, native-role Tom's Obvious Minimal
  Language files, role manifests, credentials, or installer state.

## Terms and Abbreviations

- **Astra:** GPT-6 Astra, the apex general-purpose model used by this route.
- **Codex:** OpenAI's coding-agent runtime and command-line environment.
- **Effort:** provider reasoning effort: `low`, `medium`, `high`, `xhigh`, or `max`.
- **Fallback:** an alternate route after a primary route cannot run.
- **Quality Assurance (QA):** independent verification kept outside model selection.
- **TOML — Tom's Obvious Minimal Language:** configuration format used by native roles.

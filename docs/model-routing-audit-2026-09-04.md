# Terra, Luna, Sol, and Astra Routing Audit

## Contents

- [Audit baseline](#audit-baseline)
- [Current Version 1 findings](#current-version-1-findings)
- [Astra and reasoning effort](#astra-and-reasoning-effort)
- [Version 1 decision](#version-1-decision)
- [Version 2 decision](#version-2-decision)
- [Pull-request interaction](#pull-request-interaction)
- [Terms and Abbreviations](#terms-and-abbreviations)

## Audit baseline

- Repository: `applicate2628/Orchestrarium`.
- Audited `main`: `ece04040627fcc0d0988128e44d401de53ff01fb`.
- Audited hotfix Pull Request (PR) 4 head: `3dbfb9faf824365f5898fe52dd10093f4d75da9c`; its current inline review threads are resolved.
- Audited policy-overlay PR 5 head: `ea7a9cfc21f7f5b8e78ec9681fd458917ff7aea1`; it has no model-routing file overlap.
- Official model sources: OpenAI model pages for GPT-5.6 Luna, Terra, Sol, GPT-6 Astra, and the GPT-6 Astra launch report, checked on 2026-09-04.

## Current Version 1 findings

1. `shared/role-routing-policy.v1.json` places `mechanical`, `balanced`, `frontier`, and `apex` in one order even though Luna is a zero-authority mechanical execution class rather than a lower general-reasoning tier.
2. `apex-max` names the `apex` tier but still binds `gpt-5.6-sol`; Version 1 therefore has no distinct apex model.
3. Model and effort are separate fields, but runtime selection is incomplete: native roles are static Tom's Obvious Minimal Language (TOML) bindings, while `allowedProfiles` is not a general per-dispatch model selector.
4. Exact model identifiers are repeated across role policy, native TOML, provider profile configuration, tests, and documentation.
5. There is no owner for expected cost, tokens, steps, retries, review, rework, and latency to an accepted result. Price per token alone cannot represent Astra's documented reduction in output tokens, elapsed task time, and repeated iterations.
6. Availability, explicit fallback, maximum-effort approval, safety admission, automatic fan-out, and evidence-independence are not one coherent decision.
7. Changing existing native-role TOML or the pinned Version 1 policy requires exact stock-prior installer migration. A quick Version 1 upgrade must not bypass that ownership boundary.

## Astra and reasoning effort

GPT-6 Astra supports `low`, `medium`, `high`, `xhigh`, and `max`; unlike Luna, Terra, and Sol, it does not support `none`. A model and an effort level form one exact profile. Sol `xhigh` does not automatically dominate Astra `medium`, and Astra `medium` does not automatically prove lower total cost.

OpenAI reports the published benchmark table as the maximum score at any tested effort. Therefore the published FrontierMath result cannot be attributed specifically to `medium` without separate measured evidence. At the same time, the launch report states that Astra can require fewer iterations, use fewer output tokens, and complete some agentic tasks at lower estimated task cost than Sol despite a higher per-token price. This supports Astra `medium` as the initial default for deep mathematics and connected scientific workflows, followed by measured escalation rather than automatic `xhigh` or `max`.

Effort policy for the narrow Version 1 route:

- `medium`: default for mathematical research, scientific agentic workflows, and cross-system synthesis;
- `high`: default for critical recovery, otherwise requires objective evidence that medium is insufficient or measured evidence that high improves the route;
- `xhigh`: requires objective failure or contradiction at high, or measured gain;
- `max`: requires explicit human approval for the individual run;
- `low`: evaluation or measured-sufficient route only;
- `none`: invalid for Astra.

## Version 1 decision

Add one installable, create-only `astra-routing` skill instead of changing existing native roles, the pinned Version 1 routing policy, or operator defaults.

The pure resolver:

- accepts only four admitted task classes;
- requires observed `gpt-6-astra` availability;
- resolves an exact effort with typed evidence gates;
- returns complete external Codex flags;
- permits one automatic Astra instance;
- never silently falls back;
- never authorizes acceptance, merge, or publication;
- preserves independent review and Quality Assurance (QA) gates.

This is a targeted compatibility upgrade. Existing Terra, Sol, Luna, role, sandbox, and review defaults remain unchanged.

## Version 2 decision

Version 2 must replace the linear model ranking with:

- execution class: `mechanical | general`;
- general capability: `balanced < frontier < apex`;
- exact model-effort profiles;
- one model catalog containing supported and admitted efforts;
- complete route estimates measured as expected cost and work to an accepted result;
- hard availability, fallback, maximum-effort, safety, fan-out, and evidence-independence gates;
- a pure deterministic resolver that never launches a provider.

Luna remains mechanical-only. Terra maps to balanced, Sol to frontier, and Astra to apex. Deep mathematics and connected scientific workflows default to Astra `medium`; routine or cleanly decomposable work remains on Terra or Sol unless a complete comparable estimate proves another admitted route better or an objective quality floor requires escalation.

The Version 2 optimizer must compare a complete declared candidate set. It must price every model call separately, because the long-context multiplier applies per request, and it must never let a scalar cost score override role, effort, safety, review, or availability constraints.

## Pull-request interaction

- PR 4 owns late Version 1 lifecycle, review, and publication hotfixes. The Version 1 Astra branch is stacked on its current head to avoid losing those corrections and to keep release-note/doc integration conflict-visible.
- PR 5 owns generic instruction overlays and Ponytail coexistence. It has no current file overlap and is not a dependency of either model-routing version.
- Version 2 is stacked on the final Version 1 Astra branch because it adds the full catalog and router while preserving the usable Version 1 route during migration.
- No GitHub Actions workflow is introduced or used by this work.

## Terms and Abbreviations

- **Astra:** GPT-6 Astra, the apex general-purpose model in the proposed system.
- **Effort:** the provider reasoning-effort setting: `low`, `medium`, `high`, `xhigh`, or `max` for Astra.
- **PR — Pull Request:** a request to merge a branch.
- **QA — Quality Assurance:** independent verification of implementation quality.
- **TOML — Tom's Obvious Minimal Language:** the native-role configuration format.
- **Version 1 / Version 2:** the current compatibility contract and the redesigned model-routing contract.

# Adaptive Model Portfolio Routing — Version 2 Design

## Contents

1. [Goal](#1-goal)
2. [Non-goals](#2-non-goals)
3. [Stable architecture](#3-stable-architecture)
4. [Dynamic registry](#4-dynamic-registry)
5. [Lead contract](#5-lead-contract)
6. [Portfolio slots](#6-portfolio-slots)
7. [Hard admission gates](#7-hard-admission-gates)
8. [Adaptive ranking](#8-adaptive-ranking)
9. [Diversity, scope expansion, and disagreement](#9-diversity-scope-expansion-and-disagreement)
10. [Availability and rerouting](#10-availability-and-rerouting)
11. [Decision snapshot](#11-decision-snapshot)
12. [Migration from Version 1](#12-migration-from-version-1)
13. [Testing](#13-testing)
14. [Terms and abbreviations](#14-terms-and-abbreviations)

## 1. Goal

Build a provider-neutral Version 2 routing core in which one logical Lead is hosted by Codex or Claude and selects a portfolio of interchangeable CLI workers from a dynamic runtime registry. Exact model generations are data, not policy. The router must prefer accepted-result quality, required scope coverage, independent challenge, and evidence strength before cost or latency.

## 2. Non-goals

Version 2 in this change does not:

- launch any provider process;
- manage credentials, subscriptions, billing, or quota refresh;
- transfer the Lead lease;
- apply patches or merge artifacts;
- make a model output authorizing;
- replace provider-specific containment adapters;
- hardcode current GLM, Grok, Kimi, Codex, or Claude model generation numbers;
- learn weights online or mutate policy from one run automatically.

## 3. Stable architecture

The stable system has three planes:

```text
Control plane
  logical Lead contract
  Codex Lead Host adapter
  Claude Lead Host adapter
  pure portfolio resolver

Execution plane
  dynamic CLI/runtime candidates
  provider-specific launch adapters

Evidence plane
  registry snapshots
  artifacts
  tests and benchmarks
  independent reviews
  human gates
```

Only the root Lead dispatches workers and writes work-item lifecycle state. Every worker receives one role, one bounded scope, one artifact contract, one gate contract, `maxDelegationDepth = 0`, and `authorizing = false`.

## 4. Dynamic registry

The resolver receives one immutable registry snapshot. A model entry separates:

```text
provider
provider family
runtime
lineage
exact runtime-observed model
exact effort/profile
availability
admission state
mutation ceiling
capabilities and tools
scope and approach tags
evidence metrics
```

Arbitrary future model identifiers are valid. A new GLM, Grok, Kimi, Codex, Claude, or another provider enters by producing a new registry snapshot and passing admission; stable role policy does not change.

Provider family is the diversity unit. Multiple models from the same family may provide useful competing attempts, but they count as one independent family. A registry snapshot must map one provider identifier to one provider family consistently.

Admission states are ordered:

```text
discovered < shadow < read-only < bounded-write < production
```

`quarantined` is ineligible. Admission and mutation are separate: a `production` candidate still cannot exceed its declared mutation ceiling.

## 5. Lead contract

The request names one Lead:

```json
{
  "host": "codex",
  "provider": "codex",
  "providerFamily": "openai",
  "runId": "run-123",
  "leaseEpoch": 17
}
```

Only Codex and Claude Lead Host adapters are admitted. The host/provider/family relationship is canonical. The resolver does not acquire, renew, or transfer the lease; it binds every decision to the supplied Lead identity and epoch.

A candidate from the same provider as the Lead is eligible only when `isolatedFromLead = true`. An active Lead session cannot select itself as a worker.

## 6. Portfolio slots

The task declares one or more slots. Stable role names include, but are not limited to:

```text
primary
scope-expander
challenger
implementer
reviewer
visual-validator
```

The schema permits repository-specific roles. Each slot declares:

- exact `slotId` and `role`;
- phase number;
- whether it is required;
- required capabilities and tools;
- mutation class and minimum admission;
- quality, reliability, and sample-count floors;
- artifact and gate contracts;
- slots whose artifacts are visible;
- slots from which its provider family must be independent.

A blind proposal slot has no visible upstream artifact. Cross-critique slots may see named earlier-phase artifacts. The resolver validates that visibility and independence references point only to existing earlier phases and form no self-reference.

Optional slots may remain unfilled. They are selected when they improve quality-independent scope, preferred family diversity, approach diversity, challenge evidence, or evidence strength before increasing accepted-result cost and latency.

## 7. Hard admission gates

A candidate is eligible for a slot only when all of these hold:

1. the registry and request shapes are exact and internally consistent;
2. availability is `available`;
3. admission is not `discovered` or `quarantined` and meets the slot minimum;
4. mutation ceiling meets the slot mutation class;
5. all required capabilities and tools are present;
6. quality, reliability, and sample-count floors pass;
7. same-provider Lead execution is isolated;
8. delegation depth is zero;
9. the candidate is nonauthorizing;
10. cross-slot independence constraints hold for the complete portfolio;
11. required scope tags are covered;
12. the minimum independent-family requirement is met.

No scalar score, cost estimate, or latency estimate can override a hard gate.

## 8. Adaptive ranking

The resolver enumerates the complete admitted portfolio search space up to an explicit bounded combination limit. If the complete space exceeds that limit, it returns a typed refusal rather than silently using a heuristic.

Among hard-admitted portfolios, selection is lexicographic:

1. maximize the minimum quality of required slots;
2. maximize total quality of required slots;
3. maximize desired scope-tag coverage;
4. maximize independent provider families up to the preferred count;
5. maximize distinct approach tags;
6. maximize challenge evidence;
7. maximize reliability, evidence freshness, and sample support;
8. minimize total expected accepted-result cost;
9. minimize total expected latency;
10. resolve exact ties by the ordered tuple of candidate identifiers.

Cost and latency are therefore tie-breakers after quality, scope, diversity, and evidence. A cheap portfolio cannot compensate for missing critical scope or an absent required independent review.

The numeric metrics are caller-supplied evidence in a signed or otherwise trusted registry snapshot. The pure resolver validates and compares them but does not claim they are truthful merely because they are present.

## 9. Diversity, scope expansion, and disagreement

The router selects roles, not repeated generic opinions.

```text
primary         -> main proposal
scope-expander  -> missing dimensions and alternatives
challenger      -> counterexample or failure search
implementer     -> accepted design to bounded patch
reviewer        -> independent verification
visual-validator-> visual/document/UI evidence
```

Initial proposal slots can be blind to reduce anchoring. Later cross-critique slots receive only the explicitly listed artifacts. Models do not dispatch one another or conduct an uncontrolled peer chat; all artifact flow passes through the Lead.

If selected families are below the preferred diversity count, the result is `diversityDegraded`. Policy chooses either:

- `deny`; or
- `allow-with-human-gate`.

For critical work, the latter requires an explicit human diversity gate before acceptance. Several models from one provider family never satisfy a multi-family requirement.

## 10. Availability and rerouting

Availability values include:

```text
available
not-configured
not-entitled
quota-exhausted
temporary-transport-failure
auth-invalid
contract-violation
unavailable
```

Unavailable candidates are excluded with typed reasons. If availability changes after a decision, the scheduler does not substitute a model in place. It obtains a new registry snapshot and reruns the pure resolver, producing a new decision identity and explicit reroute provenance.

A provider being unpaid or absent is a normal registry state. It degrades the available portfolio but does not invalidate the Lead workflow when another admitted portfolio satisfies hard gates.

## 11. Decision snapshot

The result includes:

- request, policy, and registry snapshot identities;
- Lead Host and lease epoch;
- selected worker per slot;
- dispatch phases and artifact visibility;
- unfilled optional slots;
- per-slot candidate exclusions;
- portfolio quality, scope, diversity, approach, evidence, cost, and latency metrics;
- diversity degradation and human-gate requirement;
- `authorizing = false`;
- a deterministic SHA-256 decision identity over the canonical request and selected portfolio.

The resolver never launches the returned plan. A separate scheduler validates the decision snapshot immediately before each provider invocation.

## 12. Migration from Version 1

The Version 1 `lead-worker-routing` request migrates to one required Version 2 slot with the same capability, mutation, tools, nonauthorizing authority, and leaf restriction. Version 1's fixed provider set is not copied into Version 2; its candidates become ordinary dynamic registry entries.

The existing Astra route remains a compatibility surface. Exact Astra, Sol, Terra, Luna, GLM, Grok, and Kimi generations are not stable V2 policy names. Any old profile alias maps to its historical model semantics and never silently changes to a newer family or generation.

## 13. Testing

Tests must prove:

- exact model generation identifiers are arbitrary registry data;
- only Codex or Claude can host Lead;
- provider-to-family inconsistencies fail closed;
- absent entitlement and quota exhaustion exclude candidates without breaking another admissible route;
- required and optional slots behave differently;
- admission, mutation, capability, tool, evidence, and isolation gates cannot be bypassed;
- multiple same-family models count once for diversity;
- independent reviewer constraints are enforced;
- required scope coverage is a hard gate;
- desired scope, approach diversity, and challenge can defeat a cheaper portfolio;
- cost and latency decide only after higher-priority criteria tie;
- degraded diversity produces the configured denial or human gate;
- complete search refuses oversized spaces rather than silently approximating;
- decision identities and CLI output are deterministic;
- malformed JSON-shaped inputs never raise uncaught exceptions.

## 14. Terms and abbreviations

- **CLI — Command-Line Interface:** provider command-line execution surface.
- **Lead Host:** Codex or Claude runtime holding the logical Lead lease.
- **Portfolio:** selected set of role-specific workers for one task.
- **Capability slot:** stable required ability independent of a model name.
- **Admission:** verified permission for a runtime to perform a class of work.
- **Provider family:** diversity unit representing one vendor/model family.
- **Blind proposal:** proposal produced without seeing peer proposals.
- **Cross-critique:** bounded review of explicitly named earlier artifacts.
- **Evidence snapshot:** immutable measured inputs used for routing.
- **SHA-256 — Secure Hash Algorithm 256-bit:** hash used to identify the canonical decision snapshot.

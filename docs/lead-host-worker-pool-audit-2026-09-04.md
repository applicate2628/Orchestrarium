# Lead Host and Interchangeable Worker Pool Audit

## Contents

1. [Audit baseline](#1-audit-baseline)
2. [Established repository behavior](#2-established-repository-behavior)
3. [Gaps in the current Version 1 route](#3-gaps-in-the-current-version-1-route)
4. [Version 1 decision](#4-version-1-decision)
5. [Version 2 correction](#5-version-2-correction)
6. [Pull-request topology](#6-pull-request-topology)
7. [Verification state](#7-verification-state)
8. [Terms and abbreviations](#8-terms-and-abbreviations)

## 1. Audit baseline

Reviewed repository surfaces:

- `main` at `ece04040627fcc0d0988128e44d401de53ff01fb`;
- Pull Request (PR) 4 at `3dbfb9faf824365f5898fe52dd10093f4d75da9c`;
- PR 5 at `ea7a9cfc21f7f5b8e78ec9681fd458917ff7aea1`;
- PR 6 at `c1bf4ba2a7c5f2c46670bc77dff2dfd91827e0da`;
- `shared/references/subagent-operating-model.md`;
- Codex and Claude Lead contracts;
- `shared/external-role-taxonomy.v1.json`;
- `shared/role-routing-policy.v1.json`;
- agents-mode schema, defaults, and presets;
- provider prompt projections and provider execution wrappers.

PR 4 remains the Version 1 lifecycle/publication hotfix base. PR 5 is an independent policy-overlay change. PR 6 is a narrow explicit Astra route stacked on PR 4.

## 2. Established repository behavior

### 2.1 Lead is already logically host-neutral

The shared operating model requires the root main conversation holding Lead to be the only downstream dispatcher and work-item lifecycle owner. It also forbids recursive wrapper launch by providers or leaves.

Codex implements Lead as an in-context skill held by the main Codex session. Claude implements the same contract as a main-session activation and explicitly refuses stale `subagent_type: lead` dispatch. Therefore the repository already supports the essential invariant:

```text
logical Lead = main conversation
Lead host     = Codex or Claude
```

A new owner role or a spawned Lead is unnecessary.

### 2.2 External roles are adapters, not professions

The external role taxonomy maps eligible research, design, implementation, QA, and reviewer roles to `external-worker` or `external-reviewer`; owner roles such as `lead` remain non-external. The shared operating model already describes the external adapters as bidirectional and allows Lead to reroute through a normal internal role when an external CLI is unavailable.

This is the correct seam for provider interchangeability: the assigned profession and artifact stay constant while the execution provider changes.

### 2.3 Current provider admission is intentionally asymmetric

The current Version 1 policy admits Codex natively, Kimi only for specified read-only task classes, and Grok only as an unavailable classifier route. Provider wrapper files exist for Codex, Claude, Kimi, and Grok, but wrapper existence does not grant execution or mutation authority.

The new resolver therefore cannot make every provider operational. It may only select routes whose current snapshot reports compatible availability, capability, tools, and admission.

### 2.4 Current model policy is not a general dynamic router

Version 1 duplicates exact model and effort choices across the role policy, native role TOML, defaults, presets, scripts, tests, and documentation. `allowedProfiles` is not a general per-dispatch selector because native role files still contain static model bindings.

PR 6 correctly avoids rewriting those ownership surfaces and adds a skill-local Astra resolver. The interchangeable worker pool must follow the same additive strategy.

## 3. Gaps in the current Version 1 route

The existing architecture does not yet provide one typed decision that separates:

- active Lead host;
- requested worker provider;
- observed runtime/model profile;
- entitlement and quota state;
- capability and tool fit;
- mutation admission;
- provider-family independence;
- fallback reason and actual selected provider.

Current auto profiles encode fixed provider orders. They do not represent a provider being normally absent because it is not paid, not configured, or temporarily out of quota. They also do not preserve a complete fallback trace when another vendor is selected.

The repository also lacks automatic Lead-host transfer, a dynamic version-independent model registry, adaptive task-specific ranking, and a first-class model portfolio for independent proposals and cross-critique. These are Version 2 concerns, not safe Version 1 point changes.

## 4. Version 1 decision

Add `lead-worker-pool` as an installable, provider-neutral compatibility skill with a pure resolver.

The resolver:

- accepts Codex or Claude as the active Lead host;
- admits only the existing Version 1 provider set: Codex, Claude, Kimi, and Grok;
- consumes caller-ranked candidates rather than hardcoding vendor priority;
- treats exact model and effort as observed provenance only;
- applies capability, tools, mutation, availability, same-host, and independence hard gates;
- distinguishes not configured, not entitled, quota exhausted, temporary failure, invalid authentication, quarantine, unavailable, and unknown;
- allows explicit cross-vendor fallback only when the caller permits it;
- preserves a complete fallback trace;
- keeps every selected route leaf-only and nonauthorizing;
- leaves existing provider wrappers and admission as the execution authority.

GLM is excluded from Version 1. The current Astra resolver remains separate and can supply an exact Codex-family candidate profile to the pool when its own route evidence admits that model.

## 5. Version 2 correction

Version 2 should replace fixed provider/model priority with three planes:

```text
control plane   = provider-neutral logical Lead hosted by Codex or Claude
execution plane = interchangeable admitted CLI workers
evidence plane  = tests, proofs, benchmarks, reviews, ledgers, human gates
```

Stable policy describes roles, capability slots, artifacts, gates, mutation classes, diversity requirements, and fallback classes. Exact model generations live only in immutable runtime/evaluation snapshots and may change without editing the stable policy.

The adaptive router should build a portfolio rather than pick one globally best model. Portfolio roles include primary, scope-expander, challenger, implementer, and reviewer. Blind proposals reduce anchoring; cross-critique is routed through Lead; empirical evidence arbitrates disagreement.

Ranking order is:

1. hard admissibility;
2. required quality floor;
3. scope and risk coverage;
4. independent challenge and marginal information gain;
5. evidence freshness and confidence;
6. expected accepted-result cost;
7. latency.

No scalar price score may compensate for missing capability, tools, mutation admission, safety, review independence, or critical scope coverage.

GLM enters only through the Version 2 provider registry and adapter. The stable policy names no GLM, Grok, Kimi, Codex, or Claude generation number.

## 6. Pull-request topology

Recommended stack:

```text
PR 4: Version 1 lifecycle/publication hotfix
  └── PR 6: explicit Astra Version 1 route
        └── Lead Worker Pool Version 1 PR
              └── Adaptive Lead Contract Version 2 documentation PR
```

PR 5 remains independent and must be integrated according to its own ownership and merge policy. No GitHub Actions workflow is added or used.

## 7. Verification state

Completed in the isolated focused fixture:

```text
23 passed
Python compilation passed
```

The focused suite verifies resolver behavior and skill metadata. The environment could not clone GitHub, so complete-checkout provider-pack validators, installer checks, `git diff --check`, and the publication gate remain required before either draft leaves review.

## 8. Terms and abbreviations

- **CLI — Command-Line Interface:** non-interactive provider execution surface.
- **Lead Host:** the Codex or Claude main conversation that currently holds logical Lead.
- **Worker pool:** available provider routes that can realize the same admitted worker contract.
- **Capability slot:** stable required ability independent of model generation.
- **Fallback trace:** ordered explanation of rejected routes and the selected substitute.
- **Provider family:** vendor lineage used to assess independence.
- **PR — Pull Request:** proposed branch merge.
- **TOML — Tom's Obvious Minimal Language:** native Codex role configuration format.

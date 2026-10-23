# Adaptive Provider-Neutral Lead and Model Routing — Version 2 Design

Historical audit baseline: main 68ad6e733e049ad3f86b37af59ea806e8d1a5b25 (2026-10-21).
Integration base: main cc570f2df858b7ab34a7922becc10fbc53f32b76; scope reconciled 2026-10-23.
Status: main-aligned design revision; not implemented runtime acceptance.
The [ownership map](../../model-routing-v2/current-main-delta.md) and
[replacement plan](../plans/2026-09-04-adaptive-lead-model-routing-v2-implementation.md)
define the integration boundary. Existing schema bundles retain their original
shape guarantees as deferred host-protocol design. See the complete
[contract scope map](../../model-routing-v2/contract-scope.md); the initial pure
comparison uses the existing owner's in-memory inputs, not these wire envelopes.

## Contents

1. [Decision](#1-decision)
2. [Stable architecture](#2-stable-architecture)
3. [Lead continuity](#3-lead-continuity)
4. [Dynamic registry](#4-dynamic-registry)
5. [Portfolio roles](#5-portfolio-roles)
6. [Structured disagreement](#6-structured-disagreement)
7. [Adaptive selection](#7-adaptive-selection)
8. [Fallback and diversity](#8-fallback-and-diversity)
9. [Contracts and migration](#9-contracts-and-migration)
10. [Acceptance criteria](#10-acceptance-criteria)
11. [Terms and abbreviations](#11-terms-and-abbreviations)

## 1. Decision

Orchestrarium Version 2 uses one provider-neutral logical Lead contract. A currently admitted Lead Host adapter may be Codex, Claude, or a future implementation; stable policy does not enumerate permanent Lead vendors. Optional Command-Line Interface (CLI) workers are selected from an immutable runtime registry snapshot. A provider may be configured, absent, unpaid, quota-exhausted, temporarily unavailable, degraded, or quarantined without breaking the logical Lead workflow.

The router constructs a role-specific model portfolio rather than choosing one universal winner. The objective is an accepted, well-covered, independently challenged, and verifiable result. Cost and latency are considered only after hard admission, quality, scope, diversity, and evidence requirements.

Current role policy owns admitted exact model/profile combinations. The comparison algorithm uses capabilities, admission, freshness, quality floors, approach diversity and provider independence without hard-coded model-generation branches. Evidence snapshots bind the applicable policy revision; they cannot override it.

## 2. Stable architecture

Existing Lead and work-item ownership feed current admission and a bounded,
pure portfolio comparison. Existing provider adapters execute authorized leaf
work; existing provenance, receiving and review owners supply evidence for Lead
synthesis and the existing human publication gate.

No parallel control plane, scheduler, review store or execution ledger is required.
A new mechanism must demonstrate a missing capability that data or an existing
owner cannot supply.

The stable invariants are:

- one active logical Lead per work item;
- Lead Host adapter, worker runtime, provider family, lineage, model identity, and effort are separate facts;
- one worker receives one assigned role, one bounded scope, one artifact contract, and one gate contract;
- workers have zero delegation depth and no acceptance, merge, release, publication, or Lead-transfer authority;
- a worker result is a claim plus an artifact, never accepted proof;
- fallback cannot silently alter role, scope, tools, mutation rights, artifact, gate, or independence requirements;
- model output cannot override empirical evidence or human policy.

## 3. Lead continuity

Current work-item ownership remains authoritative for the initial integration. Transferable ownership is a deferred extension, not a prerequisite for profile comparison or multi-model work. Local transaction locking is not proof of cross-host fencing.

If host transfer is admitted, the Lead is a durable logical role rather than a permanent process or vendor. The retained `leadLease` design contract binds the work item, lease identifier, monotonically increasing epoch, Lead Host adapter, holder run, policy snapshot, registry snapshot, acquisition time, expiry time, and state.

Host transfer requires:

1. release or expiry of the previous lease;
2. creation of a higher epoch;
3. restoration of durable roadmap, brief, status, plan, accepted artifacts, open findings, dispatches, and evidence;
4. revalidation of outstanding dispatches against the new lease and current snapshots;
5. rejection of stale writes from lower epochs.

Two hosts may observe the same work item, but only the current lease holder may mutate orchestration state. These are required guarantees for future interchangeable hosts, not a claim that the current implementation prevents cross-host split brain.

## 4. Dynamic registry

The `modelRegistrySnapshot` is retained design material for immutable comparison input. No live registry service, background discovery or new database is implied. Current admission owners remain authoritative. Only fields actually consumed by a feature need a mapped, validated producer; unavailable measurements remain unknown. The retained full runtime-entry design records:

- provider adapter and runtime identity;
- provider family and model lineage;
- runtime-observed exact model identity;
- Lead and worker capability;
- availability and entitlement state;
- admission state and mutation ceiling;
- supported and admitted effort values;
- tools and nested, effort-specific capability evidence;
- approach tags and independence groups;
- evidence freshness;
- per-profile accepted-result cost and latency, bound to task and evaluation context.

Within the retained host-protocol design, the [effort-profile evidence contract](../../model-routing-v2/effort-profile-evidence.md)
replaces model-wide `capabilities` and `routeMetrics` with `profileEvaluations`.
Selection, effort mapping, and returned results bind the same exact profile
identifier. Execution class is separate from effort and mutation rights. Schema
shape checks do not replace the required cross-record evidence validator.

Availability states distinguish ordinary scheduler conditions from hard failures. Admission progresses through `discovered`, `shadow`, `read-only`, `bounded-write`, and `production`; regressions may move an entry to `degraded` or `quarantined`.

A newly released Kimi, Grok, GLM, Codex-line, Claude-line, or future model may inherit only a lineage prior. It does not inherit production admission or benchmark results automatically. Changed models, agent harnesses, tools, permissions, or target repositories can make evidence stale and require re-evaluation.

## 5. Portfolio roles

A route request may contain these stable portfolio roles:

- `primary` — proposes the main solution;
- `scope-expander` — finds omitted factors, adjacent alternatives, hidden assumptions, and applicability limits;
- `challenger` — tries to falsify the primary proposal and supplies a competing mechanism;
- `implementer` — converts an accepted design into a bounded durable artifact;
- `reviewer` — independently checks the integrated result;
- `visual-validator` — checks visual, document, or interface states.

Each slot binds the canonical Orchestrarium role, scope and digest, required capabilities and tools, mutation class, artifact and gate contracts, input-visibility rule, challenge edges, independence edges, and an explicit candidate set. Optional slots may be omitted only with a recorded reason showing that quality and diversity requirements remain satisfied.

Interchangeability is contract-level, not competence-level. A fallback worker must satisfy the same slot contract, but model priority remains task-specific and evidence-driven.

## 6. Structured disagreement

Uncontrolled peer chat is not the debate mechanism. The Lead manages an artifact graph:

1. **blind proposals** — initial workers do not see each other's drafts, reducing anchoring;
2. **scope expansion** — a dedicated worker reports missed requirements, regimes, interfaces, assumptions, and alternatives without silently enlarging accepted scope;
3. **cross-critique** — workers inspect named artifacts and return assumptions, contradictions, failure cases, missing evidence, and implementation risks;
4. **Lead synthesis** — the Lead separates sourced facts, proved deductions, numerical observations, engineering heuristics, and hypotheses, then combines compatible parts;
5. **empirical arbitration** — tests, proofs, counterexamples, profilers, benchmarks, integration checks, and visual evidence settle testable disagreements.

Additional workers are selected by expected **marginal information gain**: new scope, a distinct approach, or a new failure class. Another highly correlated answer has lower value than a qualified worker with different approach tags and evidence independence.

Majority agreement is not truth. In the retained deferred host-protocol contracts, every unresolved contradiction prevents `selected` status and requires `humanGateRequired = true` in a degraded or blocked decision; the operational envelope also requires the human-gate contract. This retained rule is stricter than a critical-only rule. It is not the escalation policy of the initial comparator: that comparator reports evidence conflicts to the existing Lead/review owners, resolves missing facts where possible, and requests user intervention only when current governance requires it. A gate request is not acceptance or execution permission; the trusted owner must verify the corresponding evidence.

## 7. Adaptive selection

Hard gates run before optimization:

- current work-item ownership; an exact Lead lease and fence additionally apply when host transfer is supported;
- provider adapter admission;
- availability and entitlement;
- model and effort support and admission;
- role and capability eligibility;
- mutation ceiling and sandbox;
- required tools;
- safety controls;
- evidence freshness;
- zero delegation depth and nonauthorizing authority;
- required independence edges.

After hard gates, selection is lexicographic:

1. `hard-admissibility`;
2. `quality-floor`;
3. `scope-coverage`;
4. `independent-challenge`;
5. `evidence-quality`;
6. `accepted-result-cost`;
7. `latency`;
8. `stable-id`.

A Pareto set may be constructed within one stage, but no scalar price score may override a previous stage. Accepted-result cost includes calls, repeated context, retries, failed routes, rework, review, and integration—not only token price.

The proposed comparison result binds current ownership, policy and evidence revisions, route request, complete declared candidate sets, selection order, recommended assignments, rejected candidates, diversity, contradictions and applicable human-gate state. It is nonauthorizing and does not launch work. Identical validated snapshots and request data must produce the same result. Execution identities and terminal evidence belong to existing execution/receiving owners. The retained original schema additionally requires lease bindings; the initial lease-free in-memory comparison must not pretend to validate against that original shape. A new persisted format requires a demonstrated consumer and an explicit versioned contract, not another speculative envelope.

## 8. Fallback and diversity

Ordinary availability failures—unconfigured provider, missing entitlement, exhausted quota, temporary transport failure, or ordinary unavailability—may advance to the next explicit admitted candidate without changing the slot contract.

Authentication failure, adapter or contract violation, unsafe output, unmet quality floor, and exhausted budget have distinct dispositions. They must not collapse into one retry loop. A contract violation rejects the result and can degrade or quarantine admission. A quality failure causes re-planning, changed model or effort, or changed decomposition. Budget exhaustion stops explicitly; it never silently weakens quality or mutation guarantees.

Provider-family count is a coarse diversity measure. The registry also records independence groups and approach tags to avoid counting correlated lineages or repeated methods as independent insight. Diversity can be:

- `fulfilled`;
- `degraded` with explicit reasons and policy disposition;
- `not-required`.

Critical work with degraded required diversity must require a human gate. Several models from one provider family may improve redundancy but do not satisfy a cross-family review requirement.

## 9. Contracts and migration

The Draft 2020-12 schema bundle defines:

1. `leadLease`;
2. `modelRegistrySnapshot`;
3. `routeRequest`;
4. `dispatchSpec`;
5. `routeDecision`;
6. `workerResult`.

The existing run ledger remains the provenance owner. Identify which required comparison references are genuinely missing before proposing a narrow versioned extension. Do not add a parallel ledger or demand lease/epoch fields before host transfer is admitted. Existing events remain backward-readable and must not be reinterpreted as evidence they never recorded.

A Version 1 dispatch maps to one Version 2 portfolio slot only when Lead ownership, assigned role, scope, capability, mutation, tools, provider-family exclusions, artifact, gate, leaf-only delegation, and nonauthorizing authority are preserved exactly. GLM or any other new provider capability remains unavailable until its existing admission and adapter owners explicitly support it; catalog presence alone grants nothing.

This documentation slice does not implement schedulers, provider launchers, ledger migration, or admission transitions. Implementation extends current owners through separately reviewed, bounded changes.

## 10. Acceptance criteria

Each runtime slice requires its applicable contracts and existing publication gates. Requirements tied solely to deferred host transfer are not prerequisites for a pure comparison slice:

- retained schema bundles and their selected record definitions pass Draft 2020-12 validation;
- model/effort/task/context joins and whole-route accounting meet the effort-profile contract;
- normative examples validate;
- the provider-neutral algorithm contains no model-generation branches, while current policy retains explicit admitted profiles;
- current ownership is bound; host-transfer slices additionally test one active lease and stale-epoch rejection;
- availability, entitlement, admission, contract, safety, quality, and budget failures remain distinct;
- portfolio slots preserve role, scope, tools, mutation, artifact, gate, and independence;
- critical diversity degradation forces the configured human gate;
- route decisions are deterministic from immutable snapshots;
- worker results remain leaf-only and nonauthorizing;
- existing ledger, provider, review, work-item and publication owners are reused; each necessary extension has a reviewed compatibility and rollback plan.

## 11. Terms and abbreviations

- **CLI — Command-Line Interface:** command-line provider execution surface.
- **Lead Host adapter:** provider-specific implementation of the logical Lead contract.
- **Lead lease:** exclusive epoch-numbered ownership record for one work item.
- **Capability slot:** stable required ability independent of model naming.
- **Model portfolio:** workers assigned complementary roles in one routed task.
- **Admission:** verified permission for a runtime to perform a class of work.
- **Cross-critique:** controlled criticism of named artifacts by other workers.
- **Marginal information gain:** expected new information added by another worker.
- **Empirical arbitration:** resolution through tests, measurements, proofs, or other objective evidence.
- **Pareto set:** candidates not simultaneously dominated on all compared criteria within one ranking stage.

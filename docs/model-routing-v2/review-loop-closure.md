# Deep Review Loop Closure — Adaptive Lead and Model Routing V2

## Contents

1. [Purpose](#1-purpose)
2. [Accepted architectural corrections](#2-accepted-architectural-corrections)
3. [Cross-contract invariants](#3-cross-contract-invariants)
4. [Execution and provider boundaries](#4-execution-and-provider-boundaries)
5. [Review, disagreement, and synthesis](#5-review-disagreement-and-synthesis)
6. [Deliberately deferred work](#6-deliberately-deferred-work)
7. [Acceptance gate](#7-acceptance-gate)
8. [Terms and abbreviations](#8-terms-and-abbreviations)

## 1. Purpose

This addendum records the final conclusions of adversarial review loops over the Version 1 Lead/worker resolver and the Version 2 semantic and operational contract drafts. It adds no runtime behavior and grants no provider, model, tool, or mutation authority. This is a developer handoff, not runtime enforcement. Text-presence tests do not prove execution safety or independently reviewed acceptance.

The actionable checklist is [runtime-validation-obligations.md](runtime-validation-obligations.md); implemented local shapes remain owned by [the core and operational bundles](README.md).

The governing principle is proportionality: close contract gaps that could create false authority, stale ownership, fabricated independence, silent scope drift, or untraceable execution; defer optimizers and distributed machinery that are not required to make the design implementable.

## 2. Accepted architectural corrections

1. The logical Lead is provider-neutral and has exactly one active lease holder per work item.
2. Codex and Claude are initial Lead Host adapters, not permanent architecture-level model pins.
3. Direct Lead work is legal for routine tasks and must not be represented as a fictitious worker dispatch or independent opinion.
4. Exact model generations live only in immutable registry and execution snapshots.
5. A route decision is stage-local: it selects only leaf tasks whose complete inputs already exist.
6. Later challenge, implementation, review, and synthesis stages consume persisted prior artifacts through a new decision.
7. Semantic routing records own role, scope, candidates, quality, artifact, gate, and independence obligations.
8. Operational envelopes may narrow execution but must bind and never override the semantic record.
9. Repository content and model output are untrusted routing input; they cannot widen provider, data-egress, tool, mutation, budget, destructive-action, waiver, or publication authority.
10. Cost and latency remain subordinate to admissibility, quality, scope coverage, independent challenge, and evidence quality.
11. An unavailable Lead Host blocks recoverably; no worker is promoted to Lead by fallback.
12. Human approvals, test evidence, generated-code provenance, and adaptive-evidence updates require trusted records rather than model claims.

## 3. Cross-contract invariants

Runtime validators must prove facts that JavaScript Object Notation Schema cannot prove alone:

- one active lease, monotonic epoch, atomic takeover, and stale-writer fencing;
- immutable policy, registry, evaluation, context, work-item-state, candidate-set, and contract snapshots;
- canonical digest preimages and exact identifier-to-content binding;
- registry-reference existence, freshness, and launch-time admission;
- semantic/operational record identifier and digest equality;
- stage order, ready-input membership, no same-stage future dependency, and graph acyclicity;
- required-slot coverage, optional omission evidence, diversity counts, and independence-group checks;
- exact fallback order, cumulative budgets, process settlement, result identity, and artifact verification;
- durable disposition of material findings and review of the persisted critical synthesis;
- exact human-approval principal, scope, bound digests, lifetime, and revocation;
- build/test command and environment provenance plus generated-code license and dependency checks;
- trusted evidence updates that retain failures and reject model self-scoring.

Any cross-record mismatch blocks execution or acceptance. A later stage cannot override an earlier hard denial.

## 4. Execution and provider boundaries

A provider adapter must bind the actual executable, endpoint, account, entitlement, region, retention policy, applicable terms, observed model identity, effort mapping, harness, exact tool identities and permissions, sandbox, data policy, request digest, response identity, and terminal settlement evidence.

Provider aliases are evidence states, not stable model identities. If an alias changes its backing deployment, evidence tied to the old deployment expires or degrades until re-evaluated.

A provider-native internal multi-agent feature remains inside one Orchestrarium leaf. It cannot create Orchestrarium dispatches, widen tools or data access, evade model-call and parallelism budgets, or count internal workers as independent provider families.

Workspace write authority does not authorize email, issue changes, deployment, cloud mutation, publication, purchase, or another external side effect. Such an effect requires a separate target-bound contract, authorization, idempotency rule when supported, receipt, and compensation or non-reversibility disposition.

Live timeouts and retry budgets use a monotonic clock. Coordinated Universal Time timestamps remain audit evidence, not the sole timeout mechanism.

## 5. Review, disagreement, and synthesis

Multi-model execution exists to increase useful information, not merely to reduce token cost. Portfolio roles remain distinct:

- `primary` proposes;
- `scope-expander` searches for omissions and alternatives;
- `challenger` attempts falsification;
- `implementer` creates a bounded artifact;
- `reviewer` independently verifies the integrated result;
- `visual-validator` checks visual or document states.

Initial proposals may be blind to reduce anchoring. Cross-critique is artifact-bound. Majority agreement is not proof. Tests, proofs, counterexamples, benchmarks, profilers, visual checks, and other objective evidence arbitrate testable disagreement.

Every important or critical finding receives one durable disposition: accepted, rejected with evidence, returned for re-intake or explicitly deferred by the authorized owner, or blocking. Critical synthesis is reviewed after it is persisted; component reviews alone cannot prove that Lead synthesis introduced no new error.

## 6. Deliberately deferred work

The review rejects adding these mechanisms to the documentation PR:

- a self-learning router or multi-armed-bandit optimizer;
- cryptographic signatures or distributed consensus;
- automatic inference of correlated model failures;
- a universal transaction engine for every external product;
- permanent model-generation rankings;
- automatic provider write admission;
- runtime implementation hidden inside the contract PR.

These may be evaluated later against an observed need. The current design instead records the evidence and interfaces a future implementation would require.

## 7. Acceptance gate

Accept runtime slices incrementally. A read-only single-worker slice needs trusted acquisition, contract validation, ownership/fencing, bounded execution, and result verification. Enable multi-stage scheduling, writes, external effects, adaptive evaluation, or provider-native orchestration only after that feature's separate tests and admission pass. Do not make implementation of every future subsystem a prerequisite for the first safe slice.

The current documentation contracts are nonauthorizing. Passing schema validation proves local shape only; it never grants execution or acceptance authority.

## 8. Terms and abbreviations

- **Lead Host adapter:** provider-specific implementation of the provider-neutral Lead contract.
- **Stage-local decision:** a route decision containing only tasks ready to launch from already persisted inputs.
- **Operational envelope:** execution and settlement controls subordinate to one digest-bound semantic record.
- **Monotonic clock:** a clock that does not move backward and is suitable for elapsed-time budgets.
- **Provider alias:** a provider-controlled model name whose backing deployment may change.
- **External side effect:** mutation outside the bounded local workspace, such as publishing, deploying, sending, or purchasing.
- **Empirical arbitration:** resolution of disagreement through objective evidence rather than model voting.

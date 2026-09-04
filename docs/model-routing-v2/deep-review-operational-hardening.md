# Adaptive Routing Operational Hardening — Version 2 Deep Review

**Status:** normative documentation-stage supplement. It refines the existing Version 2 routing design without implementing a scheduler, changing Version 1 behavior, widening provider admission, or making telemetry self-authorizing.

## Contents

1. [Review result](#1-review-result)
2. [Confirmed contract gaps](#2-confirmed-contract-gaps)
3. [Stable semantic axes](#3-stable-semantic-axes)
4. [Lead fencing and failover](#4-lead-fencing-and-failover)
5. [Data-governance boundary](#5-data-governance-boundary)
6. [Portfolio and concurrency budgets](#6-portfolio-and-concurrency-budgets)
7. [Typed fallback and rejection](#7-typed-fallback-and-rejection)
8. [Write, retry, and replay safety](#8-write-retry-and-replay-safety)
9. [Disagreement and outcome feedback](#9-disagreement-and-outcome-feedback)
10. [Cross-record validator obligations](#10-cross-record-validator-obligations)
11. [Implementation order](#11-implementation-order)
12. [Rejected overengineering](#12-rejected-overengineering)
13. [Terms and abbreviations](#13-terms-and-abbreviations)

## 1. Review result

The original Version 2 contract bundle correctly separates the logical Lead, runtime registry, route request, dispatch, decision, and worker result. It also correctly places quality, scope coverage, independent challenge, and evidence before cost.

The deep review found that several operational boundaries were still described only in prose or were absent from machine contracts. The companion schema [`adaptive-routing-operational.v2.schema.json`](adaptive-routing-operational.v2.schema.json) adds bounded envelopes around the core contracts instead of rewriting the core bundle prematurely. The matching [`operational-examples.v2.json`](operational-examples.v2.json) provides validating, nonauthorizing examples.

## 2. Confirmed contract gaps

| Severity | Gap | Why it matters | Contract response |
|---|---|---|---|
| P1 | Dispatches carried a lease identifier but not a self-contained epoch fence | A stale host could replay work after Lead transfer | `leadFence` binds lease, epoch, holder, snapshots, expiry, and fencing digest |
| P1 | Literal provider effort was not separated from semantic effort intent | Different providers expose incompatible effort scales | `effortIntent` and explicit `effortMapping` with `exact`, `rounded-up`, or `saturated` disposition |
| P1 | Provider-native multi-agent execution could be confused with reasoning depth | More agents and deeper reasoning are different resource and authority choices | `orchestrationMode` is a separate axis and provider-native mode requires admission evidence |
| P1 | Model ranking lacked an explicit data-egress policy contract | Fallback could send sensitive context to an otherwise high-ranked but forbidden provider | `providerPolicy` binds allowed/forbidden families, regions, retention, source-code, web, and secret constraints |
| P1 | Unresolved contradictions could coexist with a selected decision | A route could appear accepted while a material dispute remained open | `decisionControl` forbids selected status with unresolved contradictions and requires a human gate otherwise |
| P1 | Fallback and rejection arrays were structurally generic | Availability, quality, safety, budget, and contract failures could collapse into one retry path | Typed `fallbackEvent` and `candidateRejection` records |
| P2 | Portfolio size, parallelism, retries, calls, wall time, and cost had no hard envelope | Optional model diversity could become an unbounded swarm | `resourceBudget` |
| P2 | Write dispatches lacked common precondition, allowed-path, rollback, and commit boundaries | Interchangeable workers could mutate different targets or make retries unsafe | `writeBoundary` plus idempotency, deadline, attempt, and adapter-admission fields |
| P2 | Adaptive routing had no accepted-outcome record | Rankings could not be updated from actual accepted work without ad hoc telemetry | `routeOutcome` |
| P2 | Candidate-set completeness was only a declaration | A router could optimize over a selectively omitted set | Digest and evidence reference with `verified-complete` disposition |

`P1` means the gap can invalidate correctness, authority, confidentiality, or failover safety. `P2` means the gap can materially damage operability, reproducibility, or adaptive quality.

## 3. Stable semantic axes

Version 2 must keep three axes separate:

```text
capability requirement
effort intent
orchestration mode
```

A role policy states capability floors and a provider-neutral effort intent:

```text
minimal | balanced | deep | extended | maximum
```

The provider adapter maps the intent to one concrete runtime effort and records exactly one mapping disposition:

```text
exact | rounded-up | saturated
```

There is no silent round-down. An unsupported quality floor is a typed route rejection, not permission to weaken the request.

Orchestration mode is independent:

```text
single-worker
managed-portfolio
provider-native
```

`provider-native` requires its own admission evidence. It is never inferred from a high effort setting, and it does not grant a leaf worker recursive delegation authority.

## 4. Lead fencing and failover

A lease identifier alone is insufficient for a self-contained dispatch. Every route, dispatch, decision, and outcome envelope binds the current:

- work item;
- lease identifier;
- monotonically increasing epoch;
- Lead Host adapter;
- holder run;
- policy, registry, and evaluation snapshots;
- fencing-token digest;
- active state and observed expiry.

The epoch and fencing token are authoritative against stale writes. Wall-clock expiry is a recovery input, not a substitute for atomic ownership. A transferred Lead must revalidate or cancel outstanding dispatches before using their results.

## 5. Data-governance boundary

Provider quality never overrides organization policy. Before candidate ranking, the route binds:

```text
allowed provider families
forbidden provider families
allowed regions
zero-data-retention requirement
sensitive-source-code permission
external-web permission
secret-material exclusion
egress-policy evidence
```

The context sent to a worker is identified by a manifest digest and evidence reference. A fallback may change the worker realization only if the replacement satisfies the same data policy. Secret material is never admitted through this generic routing contract.

Provider family lists are not sufficient by themselves: the runtime validator must also verify the exact adapter, account, region, endpoint, retention mode, and current policy evidence.

## 6. Portfolio and concurrency budgets

Diversity is useful only when it buys new evidence. The route therefore binds hard limits for:

- portfolio slots;
- simultaneous dispatches;
- total model calls;
- attempts per slot;
- wall-clock duration;
- accepted-result cost.

Parallelism should be spent on independent scope, approaches, and review—not duplicated expensive reasoning over identical context. The scheduler must stop explicitly when a hard budget is exhausted; it may not silently lower quality, remove a required reviewer, or widen data egress.

Cross-field relations such as `maxParallelDispatches <= maxPortfolioSlots` belong to the runtime validator because JavaScript Object Notation Schema cannot compare arbitrary sibling numeric values.

## 7. Typed fallback and rejection

Fallback is not one generic retry mechanism.

| Failure class | Permitted disposition |
|---|---|
| `availability-fallback` | next explicit candidate |
| `provider-hard-failure` | operator attention, quarantine, or block |
| `quality-replan` | return to planning or change decomposition |
| `safety-quarantine` | quarantine |
| `budget-stop` | block |
| `contract-denial` | block |

Every event carries its slot, source and replacement runtime where applicable, stable error identifier, evidence reference, timestamp, and disposition. Authentication, containment, contract, and unsafe-output failures never reuse untrusted output.

Candidate rejection separately records the gate stage and reason class so later evaluation can distinguish an unavailable model from a model that failed capability, independence, data, freshness, or quality requirements.

## 8. Write, retry, and replay safety

A write-capable dispatch requires a common `writeBoundary`:

- isolated workspace reference;
- exact-root digest;
- allowed-path-set digest;
- precondition digest;
- postcondition contract;
- rollback policy;
- commit policy;
- explicit destructive-operation permission.

Every dispatch also binds a deadline, attempt ordinal, maximum attempts, idempotency key, adapter-admission evidence, and immutable dispatch-spec digest.

A retry is a new attempt under the same admitted logical dispatch, not a free duplicate mutation. The scheduler must verify the precondition before every attempt and must not retry an ambiguous write whose completion state is unknown.

## 9. Disagreement and outcome feedback

A selected decision may not contain an unresolved contradiction. A degraded or blocked decision may retain unresolved contradictions only with an explicit human-gate contract.

The route outcome records objective evidence and measured results:

- whether the quality criteria were met;
- scope-coverage score;
- accepted challenge findings;
- defects found;
- rework cycles;
- model calls and tool failures;
- accepted-result cost;
- latency;
- human-gate resolution.

Outcome data updates future evaluation snapshots only through a reviewed evaluation owner. Telemetry does not directly mutate role policy, provider admission, or governance. This prevents an adaptive feedback loop from silently reinforcing benchmark bias or lowering safety requirements.

## 10. Cross-record validator obligations

Schema validation is necessary but insufficient. The runtime validator and persistence owner must additionally prove:

1. one active Lead lease per work item;
2. monotonic epochs and valid lease transitions;
3. snapshot existence, content identity, freshness, and trust source;
4. unique runtime entries, slots, dispatches, attempts, and outcomes;
5. `admittedEfforts` is a subset of `supportedEfforts`;
6. admission state is compatible with mutation ceiling and route impact;
7. allowed and forbidden provider sets are disjoint;
8. selected adapters satisfy region, retention, source-code, web, and endpoint policy;
9. candidate runtime references exist and candidate sets are complete for the declared policy;
10. challenge and independence edges reference existing non-self slots;
11. required slots are filled exactly once;
12. required independence and approach coverage are actually achieved;
13. budgets are internally consistent and not exceeded;
14. every dispatch and result matches the current Lead fence and bound digest;
15. write preconditions, postconditions, rollback, and idempotency rules hold;
16. unresolved contradictions, quality failures, and human gates have consistent status;
17. outcome evidence is objective and not authored solely by the worker being scored.

These checks belong to focused validators and persistence owners, not one giant provider adapter.

## 11. Implementation order

The minimum safe sequence is:

1. semantic `capability`, `effortIntent`, and `orchestrationMode` types;
2. Lead lease persistence and fencing;
3. trusted policy, registry, evaluation, and data-policy snapshots;
4. core-contract plus operational-envelope validator;
5. pure deterministic resolver;
6. bounded scheduler with typed fallback;
7. write-boundary and idempotency owner;
8. worker-result normalization and empirical-arbitration flow;
9. route-outcome ledger and evaluation snapshot builder;
10. provider adapters admitted independently;
11. shadow evaluation and staged promotion;
12. full migration, rollback, and publication gates.

Each step gets its own tests, owner, artifact, and independent review. Version 1 remains usable until parity is demonstrated.

## 12. Rejected overengineering

This review deliberately does not add:

- a self-modifying governance policy;
- an unbounded swarm;
- peer-to-peer worker task assignment;
- a universal provider adapter containing policy, transport, persistence, and evaluation;
- automatic provider admission from a model name;
- cryptographic signing before a trusted snapshot owner is designed;
- a hardcoded current-model leaderboard;
- mandatory multi-provider use for routine work.

The companion schema is an operational boundary and developer handoff, not a second scheduler implementation.

## 13. Terms and abbreviations

- **CLI — Command-Line Interface:** provider command-line execution surface.
- **Lead fence:** lease, epoch, holder, and digest tuple used to reject stale work.
- **Effort intent:** provider-neutral requested reasoning depth.
- **Effort mapping:** adapter record translating intent to a concrete provider setting.
- **Orchestration mode:** choice between one worker, a Lead-managed portfolio, and explicitly admitted provider-native orchestration.
- **Data egress:** transfer of task context outside the current trusted environment.
- **Idempotency:** property that a controlled retry does not create an unintended second effect.
- **Route outcome:** objective record of the accepted or rejected integrated result.
- **P1/P2:** review severities for correctness/security and operability/reproducibility gaps.

# Adaptive Routing Operational Hardening — Version 2 Deep Review

**Status:** normative documentation-stage supplement. It refines the existing Version 2 routing design without implementing a scheduler, changing Version 1 behavior, widening provider admission, or making telemetry self-authorizing.

## Contents

1. [Review result](#1-review-result)
2. [Confirmed contract gaps](#2-confirmed-contract-gaps)
3. [Stable semantic axes](#3-stable-semantic-axes)
4. [Lead fencing and immutable content](#4-lead-fencing-and-immutable-content)
5. [Data-governance boundary](#5-data-governance-boundary)
6. [Portfolio and concurrency budgets](#6-portfolio-and-concurrency-budgets)
7. [Typed fallback and rejection](#7-typed-fallback-and-rejection)
8. [Write, retry, and replay safety](#8-write-retry-and-replay-safety)
9. [Result admission and process settlement](#9-result-admission-and-process-settlement)
10. [Disagreement and outcome feedback](#10-disagreement-and-outcome-feedback)
11. [Cross-record validator obligations](#11-cross-record-validator-obligations)
12. [Implementation order](#12-implementation-order)
13. [Rejected overengineering](#13-rejected-overengineering)
14. [Terms and abbreviations](#14-terms-and-abbreviations)

## 1. Review result

The original Version 2 contract bundle correctly separates the logical Lead, runtime registry, route request, dispatch, decision, and worker result. It also correctly places quality, scope coverage, independent challenge, and evidence before cost.

The deep review found that several operational boundaries were still described only in prose or were absent from machine contracts. The companion schema [`adaptive-routing-operational.v2.schema.json`](adaptive-routing-operational.v2.schema.json) adds bounded envelopes around the core contracts instead of rewriting the core bundle prematurely. The matching [`operational-examples.v2.json`](operational-examples.v2.json) provides validating, nonauthorizing examples.

The core schema remains the semantic record model. The operational schema binds those records to execution, fencing, egress, budget, supervision, and evaluation constraints. A future validator must validate both; neither silently supersedes the other.

## 2. Confirmed contract gaps

| Severity | Gap | Why it matters | Contract response |
|---|---|---|---|
| P1 | Dispatches carried a lease identifier but not a self-contained epoch fence | A stale host could replay work after Lead transfer | `leadFence` binds lease, epoch, holder, snapshots, expiry, fencing digest, and digest profile |
| P1 | Snapshot names were not bound to snapshot content | Reusing an identifier for different bytes could invalidate every downstream decision | Policy, registry, and evaluation snapshot digests are required |
| P1 | Literal provider effort was not separated from semantic effort intent | Different providers expose incompatible effort scales | Provider-neutral slot effort plus explicit mapping with `exact`, `rounded-up`, or `saturated` disposition |
| P1 | One route-wide effort value could not express different roles in one portfolio | Primary reasoning, implementation, and review often need different depth | `slotEffortIntents` binds one intent and quality floor to each portfolio slot, with a route default only as policy fallback |
| P1 | A saturated provider effort could be used even when below the requested quality floor | A provider maximum is not automatically sufficient | Every selected mapping requires `qualityFloorSatisfied = true` and evidence |
| P1 | Provider-native multi-agent execution could be confused with reasoning depth | More agents and deeper reasoning are different resource and authority choices | `orchestrationMode` is separate and provider-native mode requires admission evidence |
| P1 | Model ranking lacked an explicit data-egress policy contract | Fallback could send sensitive context to an otherwise high-ranked but forbidden provider | `providerPolicy` binds allowed/forbidden families, regions, retention, source-code, web, and secret constraints; dispatch binds its digest |
| P1 | Unresolved contradictions could coexist with a selected decision | A route could appear accepted while a material dispute remained open | `decisionControl` forbids selected status with unresolved contradictions and requires a human gate otherwise |
| P1 | Terminal worker output was not independently bound to attempt, fence, supervision, or process settlement | A stale, replayed, orphaned, or partially cleaned result could be accepted | `workerResultControl` binds the result to the exact dispatch attempt, execution and admitting fences, and requires execution-kind-specific terminal settlement, cleanup, contract validation, and fence disposition |
| P1 | Fallback and rejection arrays were structurally generic | Availability, quality, safety, budget, and contract failures could collapse into one retry path | Typed `fallbackEvent` and `candidateRejection` records |
| P2 | Portfolio size, parallelism, retries, calls, wall time, and cost had no hard envelope | Optional model diversity could become an unbounded swarm | `resourceBudget` |
| P2 | Prompt and result payloads lacked route-level byte ceilings | A bounded number of calls could still create excessive cost or memory pressure | Per-dispatch prompt and result byte budgets |
| P2 | Write dispatches lacked common precondition, allowed-path, rollback, and commit boundaries | Interchangeable workers could mutate different targets or make retries unsafe | `writeBoundary` plus idempotency, deadline, attempt, cancellation, and supervision fields |
| P2 | Adaptive routing had no accepted-outcome record | Rankings could not be updated from actual accepted work without ad hoc telemetry | `routeOutcome`, explicitly limited to routing evaluation rather than merge or release authority |
| P2 | Candidate-set completeness was only a declaration | A router could optimize over a selectively omitted set | Digest and evidence reference with `verified-complete` disposition |
| P2 | Outcome metrics were not bound to the selected portfolio | Feedback could be credited to the wrong worker composition | `selectedPortfolioDigest` is required in decision and outcome |

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

The route carries a default intent for policy fallback, while every selected portfolio slot has an explicit binding to its own intent and quality-floor reference. The primary, challenger, implementer, and reviewer therefore need not share one effort level.

The provider adapter maps the slot intent to one concrete runtime effort and records exactly one mapping disposition:

```text
exact | rounded-up | saturated
```

There is no silent round-down. `saturated` means the provider cannot expose a higher setting; it is selectable only when separate evidence still proves that the slot quality floor is met. Otherwise the candidate receives an effort-mapping or quality rejection.

Orchestration mode is independent:

```text
single-worker
managed-portfolio
provider-native
```

`provider-native` requires its own admission evidence. It is never inferred from a high effort setting, and it does not grant a leaf worker recursive Orchestrarium delegation authority.

## 4. Lead fencing and immutable content

A lease identifier alone is insufficient for a self-contained dispatch. Every route, dispatch, decision, and outcome binds the current:

- work item;
- lease identifier;
- monotonically increasing epoch;
- Lead Host adapter;
- holder run;
- policy, registry, and evaluation snapshot identifiers and content digests;
- named digest/canonicalization profile;
- fencing-token digest;
- active state and observed expiry.

A terminal-result envelope separately records the execution owner and the admitting owner; [result admission](#9-result-admission-and-process-settlement) defines their transfer relationship.

The epoch and fencing token are authoritative against stale writes. Wall-clock expiry is a recovery input, not a substitute for atomic ownership. A transferred Lead must revalidate or cancel outstanding dispatches before using their results.

The named digest profile prevents two implementations from hashing different canonical byte representations while claiming the same logical digest. Its concrete algorithm and canonicalization rules belong to one separately versioned owner.

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

The context sent to a worker is identified by a manifest digest and evidence reference. The route binds the complete provider policy and its digest; each dispatch repeats the policy identifier and digest. A fallback may change the worker realization only if the replacement satisfies the same data policy. Secret material is never admitted through this generic routing contract.

Provider family lists are not sufficient by themselves: the runtime validator must also verify the exact adapter, account, region, endpoint, retention mode, and current policy evidence.

## 6. Portfolio and concurrency budgets

Diversity is useful only when it buys new evidence. The route therefore binds hard limits for:

- portfolio slots;
- simultaneous dispatches;
- total model calls;
- attempts per slot;
- prompt bytes per dispatch;
- result bytes per dispatch;
- wall-clock duration;
- accepted-result cost.

Parallelism should be spent on independent scope, approaches, and review—not duplicated expensive reasoning over identical context. The scheduler must stop explicitly when a hard budget is exhausted; it may not silently lower quality, remove a required reviewer, or widen data egress.

Cross-field relations such as `maxParallelDispatches <= maxPortfolioSlots`, accumulated call counts, and per-provider concurrency limits belong to the runtime validator because JavaScript Object Notation Schema cannot compare arbitrary sibling values or live provider state.

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

Candidate rejection separately records the gate stage and reason class so later evaluation can distinguish an unavailable model from a model that failed capability, effort mapping, independence, data, freshness, budget, contract, or quality requirements.

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

Every dispatch also binds a deadline, attempt ordinal, maximum attempts, idempotency key, cancellation identity, process-supervision policy, terminal-receipt requirement, adapter-admission evidence, and immutable dispatch-spec digest.

A retry is a new attempt under the same admitted logical dispatch, not a free duplicate mutation. The scheduler must verify the precondition before every attempt and must not retry an ambiguous write whose completion state is unknown.

Cancellation is advisory until the process supervisor confirms terminal settlement. Lead transfer or timeout therefore cannot make a result safe merely by issuing a cancel request.

## 9. Result admission and process settlement

The core `workerResult` describes the provider-produced artifact. The operational `workerResultControl` determines whether that output can enter Lead synthesis. It binds:

- result-control and result digests;
- dispatch identifier and dispatch-spec digest;
- `executionLeadFence`, identifying the ownership under which execution began;
- `admittingLeadFence`, identifying the ownership responsible for result admission;
- attempt ordinal and idempotency key;
- runtime entry;
- artifact and evidence-manifest digests;
- terminal receipt;
- supervision and cancellation identities;
- `executionKind`, `executionSettled`, and `processDisposition`, identifying the kind and disposition of terminal settlement;
- cleanup status;
- contract validation;
- fence disposition and revalidation evidence;
- output usability.

For `process` execution, `processDisposition` is `reaped` or `quarantined`. For `in-process` and `remote-job` execution it is `not-applicable` or `quarantined`; these kinds require their own trusted terminal evidence, not a fabricated local-process reaping record. The schema requires `executionSettled = true` but does not itself establish that the receipt is trustworthy.

A `current-fence` result requires the future runtime validator to establish matching execution and admitting ownership. A result completed after Lead transfer is usable only through an explicit `revalidated-after-transfer` path and bound revalidation evidence. The execution fence is retained rather than rewritten to impersonate the new owner. A stale-rejected or quarantined result is structurally unusable. The result envelope remains nonauthorizing: the responsible owner must still validate cross-record identities, receipt evidence, and the artifact itself.

## 10. Disagreement and outcome feedback

A selected decision may not contain an unresolved contradiction. A degraded or blocked decision may retain unresolved contradictions only with an explicit human-gate contract.

The route outcome records objective evidence and measured results:

- whether the quality criteria were met;
- exact selected-portfolio digest;
- scope-coverage score;
- accepted challenge findings;
- defects found;
- rework cycles;
- model calls and tool failures;
- accepted-result cost;
- latency;
- human-gate resolution.

`accepted` in this record means accepted for routing evaluation. `acceptanceScope = routing-evaluation` and `authorizing = false` prevent it from becoming merge, release, publication, or work-item authority.

Outcome data updates future evaluation snapshots only through a reviewed evaluation owner. Telemetry does not directly mutate role policy, provider admission, or governance. This prevents an adaptive feedback loop from silently reinforcing benchmark bias or lowering safety requirements.

## 11. Cross-record validator obligations

Schema validation is necessary but insufficient. The runtime validator and persistence owner must additionally prove:

1. one active Lead lease per work item;
2. monotonic epochs and valid lease transitions;
3. snapshot existence, content identity, digest profile, freshness, and trust source;
4. unique runtime entries, slots, effort bindings, dispatches, attempts, terminal results, and outcomes;
5. `admittedEfforts` is a subset of `supportedEfforts`;
6. admission state is compatible with mutation ceiling and route impact;
7. allowed and forbidden provider sets are disjoint;
8. selected adapters satisfy region, retention, source-code, web, endpoint, and secret policy;
9. candidate runtime references exist and candidate sets are complete for the declared policy;
10. every route slot has exactly one applicable effort-intent binding or an explicitly defined default application;
11. each concrete effort mapping matches the slot intent and has valid quality-floor evidence;
12. challenge and independence edges reference existing non-self slots;
13. required slots are filled exactly once;
14. required independence and approach coverage are actually achieved;
15. budgets are internally consistent and not exceeded;
16. every dispatch, attempt, and outcome binds its applicable Lead ownership and exact digests; terminal results preserve execution ownership and validate current admitting ownership, with explicit evidence for the `revalidated-after-transfer` path;
17. write preconditions, postconditions, rollback, allowed paths, cancellation, and idempotency rules hold;
18. every launched process reaches a terminal receipt and is reaped or quarantined;
19. unresolved contradictions, quality failures, and human gates have consistent status;
20. route outcome references the exact selected portfolio and objective evidence;
21. outcome evidence is not authored solely by the worker being scored;
22. adaptive evaluation never mutates governance or provider admission without its independent owner and review.

These checks belong to focused validators and persistence owners, not one giant provider adapter.

## 12. Implementation order

The minimum safe sequence is:

1. semantic `capability`, slot `effortIntent`, and `orchestrationMode` types;
2. digest/canonicalization profile;
3. Lead lease persistence and fencing;
4. trusted policy, registry, evaluation, candidate-set, and data-policy snapshots;
5. core-contract plus operational-envelope validator;
6. pure deterministic resolver;
7. bounded scheduler with typed fallback and resource accounting;
8. write-boundary, cancellation, process-supervision, and idempotency owners;
9. worker-result normalization, terminal settlement, and empirical-arbitration flow;
10. route-outcome ledger and reviewed evaluation snapshot builder;
11. provider adapters admitted independently;
12. shadow evaluation and staged promotion;
13. full migration, rollback, and publication gates.

Each step gets its own tests, owner, artifact, and independent review. Version 1 remains usable until parity is demonstrated.

## 13. Rejected overengineering

This review deliberately does not add:

- a self-modifying governance policy;
- an unbounded swarm;
- peer-to-peer worker task assignment;
- a universal provider adapter containing policy, transport, persistence, scheduling, and evaluation;
- automatic provider admission from a model name;
- cryptographic signing before a trusted snapshot owner is designed;
- a hardcoded current-model leaderboard;
- mandatory multi-provider use for routine work;
- distributed consensus for a single-user local orchestration tool;
- a second runtime scheduler hidden inside documentation contracts.

The companion schema is an operational boundary and developer handoff, not a second scheduler implementation.

## 14. Terms and abbreviations

- **CLI — Command-Line Interface:** provider command-line execution surface.
- **Lead fence:** lease, epoch, holder, snapshots, and digest tuple used to reject stale work.
- **Effort intent:** provider-neutral requested reasoning depth for a portfolio slot.
- **Effort mapping:** adapter record translating intent to a concrete provider setting.
- **Orchestration mode:** choice between one worker, a Lead-managed portfolio, and explicitly admitted provider-native orchestration.
- **Data egress:** transfer of task context outside the current trusted environment.
- **Idempotency:** property that a controlled retry does not create an unintended second effect.
- **Terminal receipt:** trusted evidence that execution reached a terminal state, specific to local-process, in-process, or remote-job execution.
- **Route outcome:** nonauthorizing objective record used to evaluate a completed route.
- **P1/P2:** review severities for correctness/security and operability/reproducibility gaps.

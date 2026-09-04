# Runtime Validation Obligations — Orchestrarium Version 2

## Contents

1. [Purpose](#1-purpose)
2. [Validation order](#2-validation-order)
3. [Lead lease, direct execution, and failover](#3-lead-lease-direct-execution-and-failover)
4. [Snapshot and digest trust](#4-snapshot-and-digest-trust)
5. [Policy precedence, registry, and provider admission](#5-policy-precedence-registry-and-provider-admission)
6. [Portfolio graph and coverage](#6-portfolio-graph-and-coverage)
7. [Fallback and budgets](#7-fallback-and-budgets)
8. [Execution and result settlement](#8-execution-and-result-settlement)
9. [Evaluation integrity](#9-evaluation-integrity)
10. [Contract evolution and error classes](#10-contract-evolution-and-error-classes)
11. [Terms and abbreviations](#11-terms-and-abbreviations)

## 1. Purpose

The Draft 2020-12 schema validates individual records. The persistence owner, pure resolver, scheduler, provider adapters, and integration owner must additionally prove cross-record and time-dependent invariants before launch or acceptance.

A schema-valid record is not automatically executable or acceptable. This document specifies implementation obligations, not runtime enforcement. Its text-presence and link tests are documentation checks only.

Use this checklist together with [the core and operational bundles](README.md) and [the operational review](deep-review-operational-hardening.md). Existing schema fields retain their current meaning. State snapshots, stage progression, approval records, external effects, and evaluation provenance below are future implementation requirements, not claims that corresponding fields or validators already exist. The current examples illustrate record shapes, not a fully runnable multi-stage trace.

## 2. Validation order

Runtime checks execute in this order:

```text
trusted acquisition
  -> schema validation
  -> identity and digest validation
  -> lease fence
  -> registry/admission validation
  -> portfolio graph and coverage
  -> budget and fallback validation
  -> launch revalidation
  -> terminal/process settlement
  -> result/integration validation
```

A later stage cannot override an earlier denial.

## 3. Lead lease, direct execution, and failover

The persistence owner must prove:

- at most one active lease per work item;
- monotonically increasing epoch;
- `previousLeaseId` references the immediately preceding released or superseded lease;
- acquisition precedes expiry and expiry is evaluated with a defined clock policy;
- every mutation is fenced by both `leaseId` and `epoch` at commit time, not only at planning time;
- takeover atomically supersedes the old lease;
- old-epoch dispatches are cancelled or explicitly revalidated;
- a result produced under an old epoch cannot close current work without a new Lead decision;
- crash recovery cannot create two writable Lead hosts;
- if no admitted Lead Host is available, the work item remains durably blocked and recoverable; no worker or reviewer is promoted automatically;
- live timeout and retry budgets use a monotonic clock; wall-clock rollback or drift cannot extend a lease or execution deadline.

Use a durable compare-and-swap or transaction boundary; a wall-clock timestamp alone is not a fence. Ownership transfer advances the lease epoch. Ordinary work-item progress uses versioned state and does not force a new ownership epoch or cancel unrelated work. New policy, registry, or evaluation content requires new immutable snapshots and explicit revalidation; do not edit an existing snapshot in place.

The Lead may execute routine work directly without constructing a fictitious worker. Runtime records must distinguish `main`/Lead execution from a worker dispatch. Direct Lead work cannot satisfy independent-family, challenger, or reviewer requirements, and a same-provider worker must still be a separately admitted isolated run.

## 4. Snapshot and digest trust

The snapshot owner must prove:

- policy, registry, and evaluation snapshot identifiers resolve to immutable trusted records;
- the stage references the exact immutable durable state used for its decision;
- state and context digests are recomputed from their exact canonical bundles;
- request, candidate-set, runtime-entry, dispatch, scope, artifact, artifact-contract, gate-contract, and result digests match the bytes they name;
- all records in one decision carry the same lease, context, policy, registry, and evaluation identities;
- referenced evidence exists, is immutable, and was produced before its declared expiry;
- canonical serialization and digest algorithms are versioned and unambiguous: object keys are ordered by the named profile, array order is preserved unless the contract declares set semantics, digest fields are excluded from their own preimage, UTF-8 and number rendering are fixed, and output uses lowercase Secure Hash Algorithm 256-bit hexadecimal;
- a self-describing record digest excludes its own digest field or is carried by an external trusted envelope; recursive self-hashing is forbidden;
- a repository-controlled file cannot impersonate a trusted global snapshot;
- semantic routing records and subordinate operational envelopes agree on the exact record identifiers and digests; operational controls may narrow execution but cannot override core role, scope, candidate, artifact, gate, quality, or independence semantics.

Before schema validation, a trusted JSON reader must reject duplicate JSON keys, non-finite numeric extensions, invalid UTF-8, excessive byte/depth/node counts, and trailing data. Timestamp fields must be checked with a Draft 2020-12 format checker; schema validation without format checking is insufficient.

## 5. Policy precedence, registry, and provider admission

Policy resolution is restrictive and auditable:

```text
hard governance/security
  -> explicit user-global operator policy
  -> project restrictions that may only narrow
  -> admitted work-item request
  -> nonauthorizing model suggestions
```

A cloned repository cannot enable an external provider, executable resolver, new region, longer retention, additional web access, larger budget, broader mutation, destructive operation, or waived gate. Human approval for degraded diversity does not waive security, data-egress, containment, credentials, or publication policy. Every human approval is a separate immutable record bound to the approving principal and authority source, exact decision/artifact digests, permitted exception scope, issue time, expiry when applicable, and revocation state; a boolean `resolved` field is never sufficient evidence by itself.

Before route selection and again immediately before launch, the registry/admission owner must prove:

- every runtime entry identifier is unique;
- model identity evidence records exact, aliased, or provider-undisclosed status; provider alias drift invalidates or degrades evidence tied to the prior observed deployment;
- `admittedEfforts` is a subset of `supportedEfforts`;
- capability identifiers are unique per entry;
- the selected worker exactly matches its registry entry, including provider, runtime, model, harness, tool surface, entry digest, effort, and independence groups;
- the selected entry is currently available, worker-capable, unexpired, and admitted for the requested mutation;
- its tools and capabilities satisfy the slot;
- read-only and bounded-write admission do not exceed their mutation ceilings;
- degraded entries follow explicit policy; quarantined, shadow, or discovered entries cannot enter production selection;
- executable identity, credentials, entitlement, account, region, endpoint, retention terms, applicable provider terms, sandbox, and containment are checked by the provider adapter;
- exact harness/tool identities, versions, permissions, and side effects match the registry tool surface; a tool name is never sufficient admission;
- model or provider substitution creates a new decision rather than mutating an admitted dispatch;
- every route is charged against the exact entitlement/quota/billing/concurrency pool it consumes; shared pools prevent false capacity diversity, self-starvation, and retry storms.

## 6. Portfolio graph and coverage

The resolver must prove:

- each `routeRequest`/`routeDecision` pair is stage-local and selects only ready-to-launch leaf tasks;
- the first stage has no prior decision, while later stages name their exact predecessor decisions;
- every later stage is bound to the immutable work-item state snapshot produced after its predecessor stages;
- every dispatch input is byte-for-byte represented in the available input manifest from that state;
- no dispatch consumes a result from another dispatch in the same stage;
- request slot identifiers and decision dispatch identifiers are unique;
- every dispatch references exactly one declared slot and candidate;
- every required slot is selected or explicitly omitted as required, which forces `blocked`;
- every optional omitted slot has a typed reason and evidence;
- `challengeTargetSlotIds`, `independenceFromSlotIds`, and input-artifact sources exist;
- target and dependency graphs contain no forbidden cycles;
- blind proposals have no target artifacts;
- challengers, reviewers, and visual validators see the exact declared target revisions and acceptance states;
- implementers consume only accepted upstream artifacts;
- Lead-accepted inputs carry non-null Lead acceptance evidence, while provisional or rejected inputs do not claim acceptance;
- artifact-contract and gate-contract content identities match the immutable bodies used by the slot, dispatch, and result;
- selected scopes are equal to or narrower than the admitted work-item scope;
- family and approach counts are recomputed from the selected portfolio;
- preferred diversity is not less than minimum diversity;
- claimed independence is checked against all configured independence groups and known error-correlation evidence;
- critical degraded diversity follows the declared human gate; every unresolved contradiction follows the current operational decision-control rule, which is stricter than a critical-only rule;
- reviewer/challenger independence is checked against the active Lead as well as referenced worker slots;
- every important or critical finding receives an accepted, evidence-rejected, re-intake/deferred, or blocking Lead disposition before synthesis can close; deferral cannot waive a mandatory acceptance criterion;
- a critical synthesis artifact is reviewed in a later stage; reviewing only its component worker artifacts cannot close synthesis risk.

## 7. Fallback and budgets

The resolver and scheduler must prove:

- the candidate set is complete according to the active policy and its digest;
- candidate order is deterministic and fallback follows that exact order;
- a fallback preserves role, scope, tools, mutation, artifact, gate, and independence constraints;
- normal availability failure is not confused with authentication, contract, safety, quality, or policy failure;
- provider hard failures set operator attention and cannot be reported as ordinary success;
- budget estimates use one unit and one pricing snapshot;
- measured and forecast metrics remain distinguishable;
- cumulative model calls, tool calls, cost, and latency do not exceed the admitted budget;
- budget exhaustion blocks or replans according to policy and never silently lowers a quality floor;
- additional portfolio slots require expected marginal information gain, not merely spare budget.

## 8. Execution and result settlement

The scheduler and adapters must prove:

- dispatch creation and launch are idempotent;
- launch rechecks the active lease epoch and current provider admission;
- execution settlement is verified for the actual execution kind: local processes require descendant cleanup/reaping; in-process and remote runs require the corresponding trusted terminal receipt rather than fictitious local process evidence;
- secrets do not enter prompts, logs, artifacts, or provenance;
- worker output is parsed as untrusted data; repository text and worker artifacts cannot inject system, developer, routing, tool, or publication authority;
- terminal result identity matches the exact dispatch and runtime entry;
- the raw provider output digest is preserved separately from the normalized worker result; every parser, truncation, redaction, or normalization transform is named and content-bound;
- terminal result stage, portfolio session, work-item state, artifact contract, and gate contract match the dispatch exactly;
- cancellation, timeout, output truncation, parser overflow, and failure are distinct terminal states and cannot leave a successful artifact claim;
- `PASS` remains a worker claim, never an authorizing decision;
- artifact digest, evidence, and gate contract are verified before integration;
- test/build evidence records the exact command, working root, toolchain/runtime versions, environment policy, exit status, and log or report digest; a worker summary is not test evidence;
- generated source and dependency changes pass repository license, provenance, attribution, vulnerability, and dependency-policy checks; a model assertion that code is original or compatible is not evidence;
- unresolved important or critical contradictions are surfaced to Lead;
- integration rechecks the lease immediately before durable mutation;
- duplicate or late terminal events cannot settle another dispatch;
- provider launch uses a shell-free argument vector, retains a provider-request digest and provider response/run identity when exposed, and scans bounded output without persisting credentials or secrets;
- provider-native internal orchestration cannot issue Orchestrarium dispatches, escape the declared tool/data boundary, or evade the route's model-call and parallelism budgets;
- any externally visible side effect binds a separate external-effect contract with exact target, authority, idempotency key where supported, terminal receipt, and compensation or non-reversibility disposition; workspace-write alone is insufficient.

Resource references are logical identifiers. They may be resolved only through the declared data policy; they are not arbitrary local file paths, shell fragments, or network locations by default.

## 9. Evaluation integrity

The evaluation owner must guard against adaptive feedback loops:

- vendor benchmarks are priors, not production proof;
- internal evaluations record harness, tool surface, effort, repository class, task class, and date;
- a new model generation does not inherit old production admission;
- evidence expires after material model, harness, toolchain, or repository changes;
- acceptance labels distinguish human preference from objective correctness;
- reviewer and benchmark bias remain visible;
- test-set leakage and repeated exposure are tracked;
- correlated failures reduce independence value even across different provider families;
- routing exploration is bounded and nonauthorizing until enough evidence exists;
- only trusted outcome owners may update routing evidence, and model self-ratings or unverified Lead preferences cannot update capability, quality, or independence scores;
- evaluation updates retain negative and abandoned outcomes so survivor bias does not silently improve a model profile.

## 10. Contract evolution and error classes

Before runtime persistence is introduced, define an immutable schema revision for every persisted record. Additive compatibility is accepted only when existing readers and validators have an explicit tested policy; a semantic rename, changed default, narrowed enum, altered digest preimage, or new mandatory invariant requires a new schema revision and migration map. Unknown revisions fail closed for writes and remain inspectable through a nonauthorizing archival reader.

Table 1 proposes error families for later component contracts; these names are not implemented error codes. Runtime implementations should preserve stable classes rather than inventing provider-specific prose.

**Table 1. Proposed runtime error families.**

| Class | Meaning | Default disposition |
|---|---|---|
| `E_V2_LEASE_*` | lease, epoch, or fencing failure | block |
| `E_V2_SNAPSHOT_*` | missing, mutable, stale, or mismatched snapshot/digest | block |
| `E_V2_REGISTRY_*` | invalid or inconsistent runtime registry | block/quarantine |
| `E_V2_ADMISSION_*` | provider, sandbox, entitlement, or mutation denial | only ordinary availability may fall back; other failures block/quarantine by subtype |
| `E_V2_PORTFOLIO_*` | missing slot, invalid graph, scope, diversity, or independence | replan/block |
| `E_V2_BUDGET_*` | budget inconsistency or exhaustion | block/replan |
| `E_V2_EXECUTION_*` | launch, timeout, cancellation, cleanup, or settlement failure | block/quarantine |
| `E_V2_RESULT_*` | result, artifact, evidence, contradiction, or gate mismatch | revise/block |
| `E_V2_EVALUATION_*` | stale, contaminated, or uncalibrated routing evidence | exclude/degrade |

Exact stable identifiers belong to the implementing component's tested contract.

## 11. Terms and abbreviations

- **Runtime validator:** component proving cross-record and time-dependent invariants.
- **Fence:** value checked at mutation time to reject stale owners.
- **Compare-and-swap:** atomic update only if the stored value still matches the expected value.
- **TOCTOU — Time Of Check To Time Of Use:** race between validation and use.
- **Idempotent:** safely repeatable without creating a second logical effect.
- **Quarantine:** exclusion of a runtime after a trust, safety, or reliability failure.

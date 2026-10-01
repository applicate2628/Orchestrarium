# Effort-specific evaluation and accepted-route economics

**Status:** normative amendment to the Version 2 draft contracts. Schema validation
checks record shape; it does not authenticate measurements, admit a provider,
execute a worker, or implement the cross-record routing validator.

## Contents

[1. Ownership](#1-ownership) · [2. Selection identity](#2-selection-identity) ·
[3. Effort policy](#3-effort-policy) · [4. Accounting](#4-accounting) ·
[5. Semantic validation](#5-semantic-validation) ·
[6. Selection and escalation](#6-selection-and-escalation) ·
[7. Migration and acceptance](#7-migration-and-acceptance) ·
[8. Terms](#8-terms)

## 1. Ownership

The existing registry owns runtime identity, availability, admission, and supported
controls. Nested `profileEvaluations` own capability and economic evidence for
one exact effort and evaluation context. There is no second model registry,
provider-specific selector, or global model-score table.

`runtimeEntry.capabilities` and `runtimeEntry.routeMetrics` are removed. An old
model-wide aggregate is not silently broadcast to all efforts. A newly observed
runtime may have an empty `profileEvaluations` array, but that does not supply
quality or cost evidence for a production dispatch.

The existing operational `effortMapping`, selected `dispatchSpec.worker`, and
`workerResult` all carry `profileEvaluationId`. The reference resolves within the
already bound registry/evaluation snapshots, not a mutable global lookup.

## 2. Selection identity

A candidate is a runtime/model **and** an admitted effort, execution class, task
class, and evaluation context. `profileEvaluationId` names that record; it is not
an authorization token. The context binds:

| Field | Why comparison needs it |
|---|---|
| `datasetSnapshotId` | Same problem distribution and held-out task cohort |
| `harnessSnapshotId` | Same agent harness, tool protocol, and retry policy |
| `promptPolicySnapshotId` | Same governing prompt and permitted policy overlays |
| `acceptanceContractId` | Same objective acceptance criteria and independent gates |
| `toolPolicySnapshotId` | Same available tools and their permitted use |
| `contextClass` | Input-size regime and context/caching assumptions |
| `billingPolicySnapshotId` | Exact billing/quota measurement and conversion rules |
| `routeShapeId` | Complete workflow being measured, including downstream review |

Model identity is inherited from the containing runtime entry. Evidence cannot be
moved to another runtime/model, task regime, effort, or material context without a
new evaluation. Public scores reported as a maximum over efforts are lineage
priors only, not evidence for a particular setting.

`executionClass` is separate from mutation rights and reasoning effort. A
`mechanical` slot still requires its exact deterministic plan and objective oracle.
A more capable general model does not automatically replace that contract.

## 3. Effort policy

Provider-supported values and operator-admitted values are distinct. The selected
effort must belong to both sets and satisfy role/task admission. Operator floors
may be stricter than provider support; they belong in policy snapshots, not in
permanent provider-neutral schema enums.

Effort intent is a requested reasoning depth, not a cross-model integer rank.
`rounded-up` or `saturated` describes a single adapter's mapping only. It never
proves that one model at a higher-named effort dominates another at a lower-named
one. Quality-floor evidence must reference the actual selected profile.

A higher effort may cause more testing, tool calls, and iterations. Do not assume
that higher effort reduces total work, or that a stronger model always uses fewer
tokens. Resolve that trade-off through matched task evidence.

An effort upgrade need not first waste a failed lower-effort run. A recorded
measurement showing higher-effort gain, or an admitted critical-task requirement,
may select it initially. Conversely, exhaustion of a budget does not authorize an
effort downgrade below the admitted quality or operator floor.

## 4. Accounting

All economic records use `accountingCoverage: whole-route-all-attempts`.
`measured`, `forecast`, and `unknown` are different evidence states. Unknown
numeric fields are null, never zero. Forecasts do not invent observed attempt,
acceptance, token, or call counts. A measured cohort records attempted and accepted
task counts, all-attempt cost, elapsed-time statistics, calls, and rework.

<a id="equation-1"></a>
For a measured cohort, the accepted-result cost in [equation (1)](#equation-1) is:

\[
\widehat C_{\mathrm{accepted}}
=\frac{\text{total cost of all attempts in the cohort}}
       {\text{number of accepted tasks in the cohort}}.\tag{1}
\]

This is an empirical metric, not a promise about a new task. When there are zero
accepted tasks, its numeric value is null and the quality gate remains unsatisfied.
Do not divide a cost that is already per accepted result by acceptance probability
again. Do not add retries or review costs again if the all-attempt total includes
them. Do not sum worker-level accepted-result ratios to estimate a whole portfolio.

The context names the complete measured route. A comparative route may use a
single stronger author or several weaker authoring steps, but it retains all
mandatory independent reviewers and publication gates. Shared tool and review
costs are attributed once using the evidence owner's policy.

Cash, subscription credits, and elapsed time are not interchangeable. Compare the
same `accountingUnit` under the same billing basis. A price/conversion policy must
be explicit and versioned; a credit quota is not an Application Programming
Interface (API) US-dollar bill. Monetary budgets cannot silently spend another
unit. Keep wall time separate unless an explicitly admitted objective converts it.

`tokenUsage` is optional observed data with an explicit normalization policy.
Uncached input, cache reads, cache writes, and output are separately recorded.
Canonical `outputTokens` includes `reasoningTokens`; the latter is a diagnostic
subset, not a second charge. Missing provider counters remain null. A provider
whose raw cache fields overlap must normalize them before recording additive cost
categories. Fixed per-token ratios alone do not price the complete route. The bound billing
policy must cover context-length thresholds, service tier, cache writes, and
tool charges. Crossing a long-context threshold can change rates for the entire
request; a short-context price ratio must not be reused for that request.

## 5. Semantic validation

The future cross-record validator is a mandatory gate, not implemented by these
JSON Schema documents. It must reject all of the following before scheduling:

| Obligation | Rejection condition |
|---|---|
| Unique identity | Duplicate runtime or profile-evaluation identifiers |
| Exact lookup | Missing profile or profile belonging to another runtime/model |
| Effort binding | Dispatch, mapping, evaluation, and observed effort disagree |
| Admission | Selected effort not both supported and admitted |
| Execution class | Slot, dispatch, profile, and runtime admission disagree |
| Task applicability | Evidence task/regime does not cover the requested task |
| Evidence ownership | Self-asserted or unverifiable observation used as accepted proof |
| Freshness | Expired evidence or changed harness/prompt/tools/context/model |
| Accounting | Incompatible units, unknown costs ranked as free, or unbound conversion |
| Cohort arithmetic | Accepted count exceeds attempted count or quotient is inconsistent |
| Token arithmetic | Negative/nonfinite counts or reasoning added twice to billed output |
| Route accounting | Failed attempts or mandatory review omitted or counted twice |
| Quality | Capability score borrowed from another effort or acceptance contract |
| Runtime result | Returned profile identity differs from the admitted dispatch |

The receipt and current Lead fence remain authoritative for attempt identity and
settlement. A worker's `profileEvaluationId`, `gateClaim`, or cost report cannot
self-authorize acceptance. Shape-valid records with broken joins are still invalid.

## 6. Selection and escalation

Keep the existing ordering: hard admission, quality floor, scope coverage,
independent challenge, evidence quality, accepted-result economics, latency, and
stable tie-breaking. Evaluate model/effort pairs before choosing a model; do not
choose the vendor first and append effort afterward.

Within a task class, compare at least the admitted default profile of each
plausible model and its adjacent admitted effort. Record sample size, paired task
identity, acceptance uncertainty, and post-review defects. A small/noisy vendor
benchmark is not a measured internal win. Use a held-out task set and fixed retry
budget; do not let a tested model alter the grading contract.

A stronger model can be selected on the first attempt where matched evidence
shows that it eliminates redundant authoring iterations or clears a necessary
quality floor. There is no fixed rule that three weaker calls imply a saving.
Price, cache reuse, tool charges, actual effort, and review/rework all matter.

One logical Lead remains the dispatcher. A capable model in an authoring slot is
not a new Lead. It may reduce repeated analysis and handoffs within its admitted
artifact boundary, but cannot absorb its own independent reviewer or recursively
spawn a worker team. Extra portfolio slots require expected new scope, a distinct
approach, or a new falsifiable challenge, not merely a larger call count.

Initially, one attempt has one fixed effort. Replanning to another effort creates
an explicitly linked new attempt and does not reset the task budget or acceptance
gates. In-request effort changes are a later adapter capability requiring exact
segment/usage evidence; provider documentation alone does not prove that the
installed native-agent or CLI path supports them. No implicit priority service,
provider-native swarm, or extra execution rights follow from an effort increase.

## 7. Migration and acceptance

This is a breaking correction to an unpublished V2 draft, not a migration of
production V1 records. Historical records without effort-specific evidence remain
readable as history, but cannot acquire new measured authority. Do not backfill
profile scores from old aggregate maxima. Existing V1 profile aliases retain their
historical meaning; changing model bindings requires its separate explicit migration.

Before runtime admission, complete the semantic tests in section 5, run the full
existing V2 suite, validate provider installation and snapshot projections, and
obtain independent review. Examples are synthetic, individually shape-valid
records; placeholder digests and separate illustrative fences are not an
end-to-end execution witness. Schema tests alone cannot close these gates.

## 8. Terms

**Effort** is the provider's reasoning-depth setting. **Profile evaluation** is
measurement or forecast for a bound model/effort/task/context. **Harness** is the
agent execution and tool environment. **Cohort** is the fixed task set used for an
evaluation. **Oracle** is an objective result check. **JSON — JavaScript Object
Notation** is the record format. **API — Application Programming Interface** is
the provider's programmatic interface. **CLI — Command-Line Interface** is a
provider command-line client. **USD** means United States dollars. **Null** means
not observed or not applicable, not zero. **Lead fence** binds the active logical
owner and snapshots so stale attempts cannot acquire authority.

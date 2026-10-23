# Contract scope and ownership

Historical audit baseline: main 68ad6e733e049ad3f86b37af59ea806e8d1a5b25 (2026-10-21).
Integration base: main cc570f2df858b7ab34a7922becc10fbc53f32b76; scope reconciled 2026-10-23.
This is design documentation, not a production registry or runtime configuration.

## Activation rule

Both original schema bundles describe the retained transferable-host protocol.
Their $defs, required fields, bounds, examples and nonauthorizing constants remain
unchanged. Their new $comment explains applicability, not validation semantics.
The initial pure comparison does NOT consume these dispatch/envelope shapes.
No existing runtime consumer of these draft bundles has been established.
Do not introduce another wire format before an actual producer/consumer needs it.

The table maps responsibilities, not byte-compatible APIs. Existing-owner means
reuse and verify that owner's public operation; it does not claim that every
draft field already exists or that its cross-record guarantees are implemented.
Any missing mapping must become an explicit minimal extension with regression
evidence, never a second state store or guessed receipt.

## Definition map

Each row applies to every property, nested object, array member, local definition
and reference within that record. Referenced top-level definitions use their own
row. Explicit field exceptions below override the inherited responsibility.

| Definition | Disposition | Responsibility |
|---|---|---|
| `leadLease` | deferred-host | Future lease owner; existing local work-item locks are not equivalent. |
| `modelRegistrySnapshot` | comparison-evidence | Existing role/task policy supplies eligibility; explicit immutable observations supply evidence. No registry service. |
| `dispatchSpec` | existing-owner-plus-deferred-binding | Existing Lead, provider adapter and ledger own dispatch. leadLeaseId is deferred; remaining fields map to existing scope, policy, profile and receiving responsibilities. |
| `routeRequest` | comparison-design | Existing Lead owns the bounded request. leadLeaseId is deferred; existing policy owns eligibility, not the snapshot itself. |
| `routeDecision` | comparison-design | Proposed pure comparison owns recommendations only. Existing Lead/review owns synthesis and gates; leadLeaseId is deferred. |
| `workerResult` | existing-owner | Existing adapter and receiving/ledger owners supply result provenance. A worker claim never accepts itself. |
| `candidateRejection` | comparison-design | Pure comparison returns typed reasons, without retries or admission changes. |
| `contradiction` | existing-owner | Existing review_loop_state.py and Lead retain finding disposition and objective arbitration. |
| `decisionControl` | existing-owner-plus-deferred-binding | Existing review and Lead own decision admission; leadFence is deferred. No parallel writable review store. |
| `digest` | shared-value | Existing owner-defined digest semantics; syntactic shape does not compute or authenticate a digest. |
| `dispatchControl` | existing-owner-plus-deferred-binding | Existing provider_prompt.py owns launch, bounds and settlement. leadFence is deferred; no replacement process supervisor. |
| `effortIntent` | comparison-evidence | Existing policy defines intent; provider adapter owns exact supported mapping. |
| `effortIntentBinding` | comparison-evidence | Existing role/task contract binds slot quality; proposed comparison may narrow only. |
| `effortMapping` | existing-owner | Existing policy and adapter own exact model-local effort and capability admission. |
| `fallbackEvent` | existing-owner | Existing dispatch/review owners classify failure and bound retries; no automatic provider change. |
| `leadFence` | deferred-host | Future lease owner; no synthetic epoch or fence for present-day execution. |
| `mutation` | shared-value | Current policy/sandbox and explicit user authority, never expanded by comparison. |
| `providerPolicy` | existing-owner | Current external taxonomy, provider adapter and user data permissions own egress. |
| `resourceBudget` | existing-owner | Existing Lead/provider bounds and user spending authority; missing cost evidence is not zero. |
| `routeControl` | existing-owner-plus-deferred-binding | Existing Lead and adapter own budget/admission; leadFence is deferred. No extra scheduler. |
| `routeOutcome` | existing-owner-plus-deferred-binding | Existing receiving/review and ledger own outcome and measurements; leadFence is deferred. |
| `timestamp` | shared-value | Owner-supplied explicit time; format validation is not freshness evidence. |
| `token` | shared-value | Owner-supplied stable identity; string validation grants no authority. |
| `workerResultControl` | existing-owner-plus-deferred-binding | Existing receiving/adapter owns settlement and identity; executionLeadFence, admittingLeadFence, fenceDisposition and transfer revalidation belong to deferred host protocol. |
| `writeBoundary` | existing-owner | Existing provider containment and publication rules own mutation/rollback; no new permission. |

## Field-level exceptions and preserved invariants

- schemaVersion and record identity stay with the defining contract. No silent
  interpretation of an old record as a new lease-free shape.
- All lease, epoch, holder, fence and transfer-revalidation fields are deferred
  host-protocol bindings. Required fields remain required in retained records.
- Snapshot identifiers/digests, exact profileEvaluationId, context and evidence
  references belong to bounded comparison provenance; authenticity, freshness,
  complete candidate sets and cross-record joins need consuming-owner checks.
- Role, scope, tools, mutation, artifact and gate fields refer to current policy,
  Lead and adapter contracts. Comparisons cannot expand them.
- Process/run/attempt/idempotency/cancellation/terminal fields belong to existing
  execution and receiving owners, not the pure comparison result.
- Contradictions, independence, finding dispositions and human gates belong to
  existing review/Lead owners. Every unresolved contradiction blocks selected
  status in retained decisions; a true gate boolean is never approval.
- Metrics, amounts, currencies, units and task/context references belong to
  evidence. Missing values remain unknown; no cross-unit cost ordering.
- authorizing stays false and maxDelegationDepth stays zero wherever defined.
  A worker result or route recommendation never grants publication or launch.

## Examples

examples.v2.json and operational-examples.v2.json remain synthetic, individually
validated examples of the deferred protocol, NOT a ready stage trace.
Their lease values are fixture data, never facts to synthesize for old runs.
For the initial comparison, use real eligibility output in future focused tests:
two admitted profiles for the same slot; unavailable or forbidden profiles;
missing quality evidence; incomparable accounting units; missing independent
reviewer; policy drift after recommendation. No provider launch is necessary.
The implementation must pin the actual producer shape before making fixtures.

## Compatibility and activation checks

Keep all existing schema negative tests, timestamp checks, input bounds,
non-authority, effort/context and result-settlement checks.
Documentation tests distinguish current-owner reuse from host transfer and check
that every retained top-level definition has a disposition.
Host transfer additionally requires actual exclusive acquisition, stale-write
rejection, crash recovery and cancellation/revalidation under concurrency.
Record-shape success does not satisfy those tests.

## Terms and Abbreviations

Definition bundle: schema library requiring an explicit selected definition.
Owner: sole authoritative producer/action for a responsibility.
Deferred: preserved design, not current mandatory runtime machinery.
API: application programming interface.

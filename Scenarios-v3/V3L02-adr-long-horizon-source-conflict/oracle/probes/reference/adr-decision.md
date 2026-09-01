# V3L02 ADR Decision

## Decision
Choice: boundary-owned-compatibility-adapter (status ADOPT).

## Source Authority
Ranking: SRC-CODE-API > SRC-RUNTIME-TRACE > SRC-DOWNSTREAM-TEST > SRC-PROPOSAL > SRC-STALE-ADR.

## Accepted Claims
- AC-1: PlanBridge owns translation and producer boundary.
- AC-2: legacy_plan_id and seat-sync.
- AC-3: idempotency_key and consumer shim.
- AC-4: v1 and 90 days.

## Rejected Options
- A: rejected due to global entitlement bus and audit correlation.
- C: rejected due to consumer-side shims and idempotency.
- D: rejected due to direct schema switch and legacy_plan_id.
- STALE-ADR-021: rejected due to stale and 14 days.

## Compatibility Plan
- CP-1: PlanEnvelopeV1, PlanEnvelopeV2, adapter.
- CP-2: legacy_plan_id, 90 days.
- CP-3: idempotency_key, producer.
- CP-4: DST-1, DST-2, DST-3, DST-4.

## Rollback Plan
- RB-1: disable v2, preserve v1.
- RB-2: idempotency, audit correlation.

## Non-Claim Ledger
- NC-1: we do not claim seat-sync / completed.
- NC-2: we do not claim global entitlement bus / approved.
- NC-3: we do not claim 14 days / current.

## Gate Decision
PASS

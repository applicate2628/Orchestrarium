Date: 2026-04-30
Source id: `SRC-DOWNSTREAM-TEST`
Authority: current downstream compatibility evidence

# Downstream Constraints

Current downstream contract tests:

| Test id | Result | Meaning |
|---|---|---|
| `DST-1` | PASS | `billing-ledger` accepts `account_ref` when `idempotency_key` is stable |
| `DST-2` | FAIL | `seat-sync` fails when `legacy_plan_id` is missing |
| `DST-3` | PASS | `support-snapshot` can store a v2 preview only if the v1 body is still present |
| `DST-4` | FAIL | a global entitlement bus replay loses PlanBridge audit correlation ids |

Compatibility window:

- Keep `PlanEnvelopeV1` available for at least `90 days` after the last listed downstream test has
  current passing evidence.
- Add `PlanEnvelopeV2` only behind a producer-owned compatibility adapter.
- The release gate must block publication if any of `DST-1..DST-4` is not addressed by the ADR.

Rollback expectation:

- Rollback must disable v2 emission while preserving v1 emission, stable idempotency, and audit
  correlation ids.

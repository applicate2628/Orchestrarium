Date: 2026-04-30
Source id: `SRC-CODE-API`
Authority: current implementation contract

# Current Code Contract

PlanBridge owns subscription-plan change translation for three current downstream consumers:

- `billing-ledger`
- `seat-sync`
- `support-snapshot`

The current public entry point is `PlanBridge.apply_plan_change(change)`.

The current output envelope is `PlanEnvelopeV1`.

Required current fields:

| Field | Status | Consumer dependency |
|---|---|---|
| `legacy_plan_id` | required | `seat-sync` still keys seat reconciliation by this field |
| `account_ref` | required | `billing-ledger` and `support-snapshot` use it for account grouping |
| `idempotency_key` | required | `billing-ledger` rejects events without it |
| `effective_at_ms` | required | all three consumers use deterministic replay ordering |

Owned boundary:

- PlanBridge owns translation and compatibility at the producer boundary.
- Consumers must not implement temporary per-consumer schema shims for this migration.
- Central routing or global entitlement-bus ownership is outside the current owning boundary.

Current invariant:

- A migration may add a v2 envelope, but it must keep the v1 envelope available until all listed
  consumers have explicit current passing evidence.

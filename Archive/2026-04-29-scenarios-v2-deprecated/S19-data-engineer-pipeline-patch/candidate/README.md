# Candidate Root

This is the mutable run root copied for each scored execution.

The only editable surface is the SQL transform in `workspace/sql/customer_day_rollup.sql`. The
start state is intentionally wrong for customer-day rollups because it keeps pending orders, does
not dedupe retried settled rows, and omits the required `refund_cents` column.

## Editable file

- `workspace/sql/customer_day_rollup.sql`

## Read-only context inside the candidate root

- `workspace/README.md`
- `workspace/data/`
- `workspace/scripts/`
- `shared-runners/`
- `infra-config/`
- `results-surfaces/`
- `existing-scenario-roots/`

The intended repair path is to keep the change inside the bundle-local SQL owner seam and validate
it with the direct local route only.

# Failing Validation Notes

The bundled start state is intentionally broken. Running the local validation route now should fail
with these scenario-level issues:

- `schema-refund-cents-column`
  The published relation is missing the required `refund_cents` column.
- `pending-orders-included`
  The `2026-03-14 / c-001` row still counts a pending order.
- `retried-order-double-counted`
  The `2026-03-14 / c-002` row still counts a retried settled order twice.

The correct fix is to repair the SQL transform, not to edit the validator, snapshots, runners, or
infra files.

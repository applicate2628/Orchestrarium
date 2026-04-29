# Expected Patch

The intended solution is a local SQL repair that keeps the published contract at
`customer_day_rollup`.

## Required repair traits

1. keep the work inside `candidate/workspace/sql/customer_day_rollup.sql`
2. dedupe retried staged rows by `order_id`, keeping the latest `ingested_at`
3. filter the published aggregate to settled orders only
4. expose the exact schema required by the contract, including `refund_cents`
5. preserve the known-good `2026-03-15 / c-003` totals while fixing the broken rows

The fix does not require backfill orchestration, deployment rewiring, result editing, or changes to
the validation script.

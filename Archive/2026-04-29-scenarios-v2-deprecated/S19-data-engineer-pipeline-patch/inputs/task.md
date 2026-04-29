# Task

Patch the bundle-local SQL transform in `candidate/workspace/sql/customer_day_rollup.sql` so the
published rollup contract becomes correct again.

## Allowed edit surface

- `candidate/workspace/sql/customer_day_rollup.sql`

## Required validation route

Run this command from `candidate/workspace/` after the patch:

```bash
python scripts/validate_customer_day_rollup.py
```

## Required outcomes

1. publish a relation named `customer_day_rollup`
2. keep the grain at one row per `business_date` plus `customer_id`
3. include only settled orders after deduping ingestion retries by latest `ingested_at`
4. expose the exact metric columns required by the schema contract, including `refund_cents`
5. leave shared runners, infra config, result snapshots, and other scenario roots untouched

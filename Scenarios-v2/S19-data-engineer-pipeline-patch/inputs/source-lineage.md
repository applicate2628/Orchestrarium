# Source Lineage

The only staged upstream relation in this bundle is `stg_orders`, loaded from
`candidate/workspace/data/stg_orders.csv`.

## Available source columns

- `order_id`
- `customer_id`
- `business_date`
- `status`
- `subtotal_cents`
- `refund_cents`
- `ingested_at`
- `batch_id`

## Lineage constraints

- do not introduce joins to shared runner metadata, infra manifests, snapshots, or other scenario
  artifacts
- do not move the fix into a scheduler, deployment job, or result export
- keep the repair as a local SQL transform that consumes only the staged bundle data

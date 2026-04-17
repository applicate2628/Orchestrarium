# Schema Contract

The published relation must be named `customer_day_rollup` and must expose these columns in this
exact order:

1. `business_date`
2. `customer_id`
3. `settled_order_count`
4. `gross_revenue_cents`
5. `refund_cents`
6. `net_revenue_cents`

## Grain

- exactly one row per `business_date` plus `customer_id`
- no duplicate rows for the same customer-day grain

## Metric rules

- count only settled orders
- dedupe retried staged rows by keeping the latest `ingested_at` per `order_id`
- `gross_revenue_cents` is the sum of settled order subtotal values
- `refund_cents` is the sum of settled order refund values
- `net_revenue_cents` equals `gross_revenue_cents - refund_cents`

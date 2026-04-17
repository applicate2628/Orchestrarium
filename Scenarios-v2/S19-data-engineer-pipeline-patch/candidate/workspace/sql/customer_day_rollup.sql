DROP VIEW IF EXISTS customer_day_rollup;

CREATE VIEW customer_day_rollup AS
SELECT
  business_date,
  customer_id,
  COUNT(*) AS settled_order_count,
  SUM(subtotal_cents) AS gross_revenue_cents,
  SUM(subtotal_cents) - SUM(refund_cents) AS net_revenue_cents
FROM stg_orders
WHERE status <> 'cancelled'
GROUP BY business_date, customer_id;

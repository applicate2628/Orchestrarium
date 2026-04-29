# Workspace

This workspace contains the bundle-local data pipeline assets for `S19`.

## Contents

- `data/stg_orders.csv` is the staged fixture data loaded into `stg_orders`
- `sql/customer_day_rollup.sql` is the only editable transform
- `scripts/validate_customer_day_rollup.py` is the direct validation route

## Validation

Run the validator from this directory:

```bash
python scripts/validate_customer_day_rollup.py
```

The validator expects the published relation to stay local, deterministic, and schema-correct.

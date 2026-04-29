# Oracle

The oracle material defines the ground-truth repair for `S19`.

## Repair truth

The correct fix stays entirely inside the bundle-local SQL owner seam. The repaired query should
publish the declared `customer_day_rollup` contract, filter to settled orders, dedupe retried
staged rows by latest `ingested_at`, preserve refund metrics, and leave orchestration, infra, and
result surfaces untouched.

## Included oracle files

- `pipeline-contract.json` provides machine-readable bundle and validation anchors
- `expected-patch.md` describes the required SQL repair shape
- `forbidden-widening.md` lists out-of-scope edits that should lose correctness or scope points
- `scoring-anchors.md` turns the scoring model into `S19`-specific pass and fail signals

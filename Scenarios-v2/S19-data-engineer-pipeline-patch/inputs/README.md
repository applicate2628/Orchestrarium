# Inputs

This directory is the immutable packet for `S19`. It describes the bounded data-pipeline task, the
schema and grain contract for the rollup, the owner seam, and the observed failing start state.

## Included materials

- `task.md` defines the scoped SQL repair and the allowed edit surface
- `owner-map.md` separates the data-owned workspace from shared runners, infra config, and results
- `schema-contract.md` defines the published rollup columns, grain, and metric rules
- `source-lineage.md` documents the only staged source relation the query may depend on
- `failing-validation.md` records the intended broken start state and expected failing checks

These inputs are data-engineering specific. A generic implementation answer that edits runners,
deployment config, snapshots, or other scenario roots should lose scope-discipline points.

# Accepted Constraints

## Allowed change surface

- `tools/status_snapshot.py`
- `tests/test_status_snapshot.py`
- `docs/cli/status-snapshot.md`

## Protected surfaces

- `Scenarios-v2/**`
- `Work/next-upgraded-pack/Results-drafts/**`
- `Archive/**`
- runner or scorer plumbing outside the status snapshot tool
- publication tables and result rankings

## Required tests and checks

- targeted tests for JSON keys, output shape, and exit behavior
- direct smoke check for `--dry-run` with explicit no-write confirmation
- nearby smoke check for the existing `--text-summary` path
- basic performance smoke on the `500-item` fixture

## Rollback expectations

- rollback stays inside the admitted delivery surface only
- if a phase fails, restore the previous `--text-summary` behavior and the `status.snapshot.json`
  filename contract before attempting a new approach
- do not compensate by editing result tables, archive history, or unrelated docs

## Deferred by policy

- schema-v2 expansion beyond the first JSON payload
- remote upload or publish hooks
- any reranking, publication-table, or archive cleanup follow-up

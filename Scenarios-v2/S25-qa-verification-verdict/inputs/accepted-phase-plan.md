# Accepted Phase Plan

## Phase goal

Add machine-readable JSON output and a `--dry-run` preview mode to the bundle-local status snapshot
tool while keeping the existing text-summary path stable.

## Allowed implementation surface

- `tools/status_snapshot.py`
- `tests/test_status_snapshot.py`

## Must-not-break surfaces

- the legacy `--text-summary` CLI output
- the no-write guarantee for `--dry-run`
- the existing output filename `status.snapshot.json` for real runs

## Planned verification

- targeted tests for JSON keys and exit behavior
- direct smoke check for `--dry-run`
- nearby smoke check for the existing `--text-summary` path
- basic performance smoke on the `500-item` fixture

## Phase acceptance

The phase passes only if all four acceptance criteria are evidenced, no unexpected file writes
occur in dry-run mode, nearby smoke coverage is present, and the performance smoke stays within the
budget.

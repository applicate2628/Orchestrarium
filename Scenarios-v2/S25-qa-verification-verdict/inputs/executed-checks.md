# Executed Checks

## Targeted automated checks

- `pytest tests/test_status_snapshot.py -q`
  - result: `3 passed`
  - read: the targeted test file covers JSON keys, dry-run exit code, and real-run file creation

## Direct functional smoke

- `python tools/status_snapshot.py fixtures/500-items.json --json`
  - result: `PASS`
  - read: emitted JSON summary and wrote `status.snapshot.json`

- `python tools/status_snapshot.py fixtures/500-items.json --dry-run --json`
  - result: `FAIL`
  - observed stdout: JSON summary printed as expected
  - observed side effect: `status.snapshot.json` was still created in the temp run directory

## QA note

The dry-run smoke is the only executed check that contradicts the acceptance criteria. The targeted
test suite did not assert file absence for dry-run mode.

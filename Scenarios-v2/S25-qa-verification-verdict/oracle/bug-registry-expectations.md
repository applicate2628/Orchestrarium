# Bug Registry Expectations

If the candidate returns `REVISE`, the QA report should state the follow-up bug that must be
recorded.

## Expected bug follow-up

- severity: `high`
- summary: dry-run mode writes `status.snapshot.json`
- reproduction anchor:
  - run `python tools/status_snapshot.py fixtures/500-items.json --dry-run --json`
  - observe that `status.snapshot.json` is created anyway

## Additional follow-up

The report should also note that nearby smoke coverage for `--text-summary` must be added before the
phase can pass, but this is a verification gap rather than a separate architecture or transport
issue.

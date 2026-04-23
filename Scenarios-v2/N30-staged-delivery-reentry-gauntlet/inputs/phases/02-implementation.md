# Phase 02 - Implementation

Fresh worker session. Resume only from files in the run root. Read `candidate/delivery-state.json`
before editing.

Repair the ReleaseFlow runtime and tests:

- `activeProfile` must beat stale `legacyProfile`.
- latest sequence wins per `changeId`.
- blocked environments are excluded.
- dependencies appear before dependents.
- crash/resume does not duplicate already-applied work.
- reports use ledger/audit state, not notifications.

Edit only the allowed source files, `candidate/workspace/tests/test_releaseflow.py`, and
`candidate/delivery-state.json`.

Tests should include these function names:

- `test_active_profile_wins_over_legacy_profile`
- `test_latest_change_wins_and_dependency_order`
- `test_crash_resume_is_idempotent`
- `test_report_uses_ledger_audit`

Run `python candidate/workspace/tests/test_releaseflow.py` before finishing and append the command to
`candidate/delivery-state.json`.

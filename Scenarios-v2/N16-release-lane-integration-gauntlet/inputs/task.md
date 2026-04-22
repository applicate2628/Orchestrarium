# Task

You are acting as an implementation worker on a long-horizon release-lane integration patch.

## Goal

Repair `candidate/workspace/src/releaseflow/` so the protected public API in
`src/releaseflow/api.py` can run release requests through configuration, intake, dedupe, planning,
scheduling, ledger, notification, rollback, audit, and reporting without losing ownership
boundaries.

## Required behavior

- Resolve the active profile from `activeProfile`; treat `legacyProfile` only as a fallback.
- Normalize request objects without mutating caller input.
- Dedupe by semantic release key: customer, service, version, lane.
- Preserve source trace from request to ledger/audit/report.
- Plan dependencies before dependents.
- Enforce canary before prod for the same customer/service/version.
- Defer frozen lanes instead of deploying them.
- Make ledger writes idempotent across repeated runs.
- Emit visible notifications exactly once per active release key.
- Roll back only the current failed deployment group.
- Derive reports from ledger and audit state, not transient notification lists.
- Preserve the public API in `src/releaseflow/api.py`.

## Allowed output

Update only:

- `candidate/workspace/src/releaseflow/config.py`
- `candidate/workspace/src/releaseflow/intake.py`
- `candidate/workspace/src/releaseflow/dedupe.py`
- `candidate/workspace/src/releaseflow/planner.py`
- `candidate/workspace/src/releaseflow/scheduler.py`
- `candidate/workspace/src/releaseflow/ledger.py`
- `candidate/workspace/src/releaseflow/notifier.py`
- `candidate/workspace/src/releaseflow/rollback.py`
- `candidate/workspace/src/releaseflow/audit.py`
- `candidate/workspace/src/releaseflow/report.py`
- `candidate/workspace/src/releaseflow/executor.py`
- `candidate/workspace/src/releaseflow/store.py`
- `candidate/workspace/tests/test_releaseflow.py`

## Disallowed behavior

- do not edit `inputs/`, `oracle/`, or `verifiers/`
- do not edit `src/releaseflow/api.py`, `src/releaseflow/__init__.py`, or `src/releaseflow/models.py`
- do not move behavior into docs, legacy helpers, UI labels, or tests only
- do not special-case verifier sequence names or read oracle files from candidate code

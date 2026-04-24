# Task

You are acting as an implementation worker responding to incident `INC-742`.

## Goal

Repair `candidate/workspace/src/deploygrid/` so the protected public API in
`src/deploygrid/api.py` can run deployment requests through configuration, intake, dedupe, planning,
policy scheduling, ledger, notification, rollback, audit, and reporting without replaying committed
side effects. Then update `candidate/reconciliation-note.md` with the source decisions and review
response that explain the repair.

## Source priority

Use these sources in order:

1. `inputs/incident-log.md`
2. `inputs/review-feedback.md`
3. `inputs/task.md`
4. `inputs/stale-requirements.md` only as a set of rejected traps

## Required runtime behavior

- Resolve the active profile from `activeProfile`; treat `legacyProfile` only as a fallback.
- Normalize request objects without mutating caller input or caller config.
- Preserve tenant, service, version, lane, window, source, and dependency trace.
- Dedupe by semantic deploy key: tenant, service, version, lane, window.
- Keep the latest request for a semantic key and audit superseded source ids.
- Plan dependencies before dependents and block dependency cycles with a causal report.
- Enforce canary before prod for the same tenant/service/version/window.
- Defer frozen tenant/lane/window scopes instead of deploying them.
- Keep ledger writes, audit rows, and notifications idempotent across repeated runs.
- Resume safely after a simulated crash after a committed step without replaying that side effect.
- Roll back only the current failed deployment group.
- Derive reports from ledger and audit state, not transient notification lists.
- Preserve the public API in `src/deploygrid/api.py`.

## Required reconciliation note

Update `candidate/reconciliation-note.md` with:

- a source arbitration section that names `INC-742`, keeps `activeProfile` as authoritative, and
  states that `legacyProfile` is fallback only
- a stale-source rejection section that rejects UI badge, legacy helper, and notification-count
  fixes
- a review response section that answers `R1`, `R2`, `R3`, `R4`, and `R5`
- a validation evidence section naming the direct verifier or test command used for the repair

## Allowed output

Update only:

- `candidate/workspace/src/deploygrid/config.py`
- `candidate/workspace/src/deploygrid/intake.py`
- `candidate/workspace/src/deploygrid/dedupe.py`
- `candidate/workspace/src/deploygrid/planner.py`
- `candidate/workspace/src/deploygrid/policy.py`
- `candidate/workspace/src/deploygrid/scheduler.py`
- `candidate/workspace/src/deploygrid/ledger.py`
- `candidate/workspace/src/deploygrid/notifier.py`
- `candidate/workspace/src/deploygrid/rollback.py`
- `candidate/workspace/src/deploygrid/audit.py`
- `candidate/workspace/src/deploygrid/report.py`
- `candidate/workspace/src/deploygrid/executor.py`
- `candidate/workspace/src/deploygrid/store.py`
- `candidate/workspace/tests/test_deploygrid.py`
- `candidate/reconciliation-note.md`

## Disallowed behavior

- do not edit `inputs/`, `oracle/`, or `verifiers/`
- do not edit `src/deploygrid/api.py`, `src/deploygrid/__init__.py`, or `src/deploygrid/models.py`
- do not move behavior into docs, legacy helpers, UI labels, or tests only
- do not claim `legacyProfile` overrides `activeProfile`
- do not count report totals from notifications
- do not special-case verifier sequence names or read oracle files from candidate code

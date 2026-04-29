# Task

You are acting as an implementation worker responding to incident `INC-742`.

## Goal

Repair the ownership-bound defect in `candidate/workspace/src/deploygrid/` so the protected public
API in `src/deploygrid/api.py` can resume deployment requests without replaying committed side
effects and can report from durable ledger/audit state after transient notifications are lost. The
visible test file is protected and must stay unchanged. Then update `candidate/repair-ledger.json`
with the source decisions, review responses, validation, and patch budget that explain the repair.

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
- Preserve hidden public report-consumer semantics through `summarize_state(state)`: a consumer with
  access only to the public API/report surface must be able to recover superseded source ids,
  deferred/frozen causes, dependency blocker causes, and whether resume avoided replay after a crash.
  Use explicit machine-readable fields named `superseded_sources`, `deferred_causes`,
  `blocked_causes`, and `resume`.
- Preserve the public API in `src/deploygrid/api.py`.

## Required repair ledger

Update `candidate/repair-ledger.json` as valid JSON with:

- `incidentId: "INC-742"`
- `sourceDecisions`: exact source arbitration rows for `INC-742`, `review-feedback`, and the stale
  UI, legacy, and notification-count traps
- `reviewResponses`: exact `R1` through `R5` rows with accepted/rejected status and owner files
- `validation.commands`: the verifier or test command you ran
- `patchBudget.maxChangedPaths`: `3`
- `patchBudget.requiredChangedPaths`: exactly these three paths:
  - `candidate/workspace/src/deploygrid/executor.py`
  - `candidate/workspace/src/deploygrid/report.py`
  - `candidate/repair-ledger.json`

The scope gate will compare actual changed paths with this JSON. A runtime-correct broad rewrite is
still a failed answer for this scenario.

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
- `candidate/repair-ledger.json`

## Disallowed behavior

- do not edit `inputs/`, `oracle/`, or `verifiers/`
- do not edit `src/deploygrid/api.py`, `src/deploygrid/__init__.py`, or `src/deploygrid/models.py`
- do not edit `candidate/workspace/tests/test_deploygrid.py`; it is an immutable visible test
- do not move behavior into docs, legacy helpers, UI labels, or tests only
- do not claim `legacyProfile` overrides `activeProfile`
- do not count report totals from notifications
- do not special-case verifier sequence names or read oracle files from candidate code
- do not broaden the patch beyond the owner files required in `candidate/repair-ledger.json`

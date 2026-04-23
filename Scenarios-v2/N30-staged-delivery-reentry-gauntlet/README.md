# N30 Staged Delivery Re-Entry Gauntlet

`N30` benchmarks a worker on a staged delivery task that spans separate sessions over one disposable
bundle copy. Each phase is launched as a fresh worker invocation against the same run root, so the
candidate must persist useful state in the bundle instead of relying on chat continuity.

The target is a small release-flow package with defects in profile precedence, release planning,
resume/idempotency, and reporting source of truth. The candidate must repair the runtime, add
meaningful tests, respond to a review packet, and close with a machine-readable delivery record.

## Expected candidate work

Across the four phases, edit only:

- `candidate/delivery-state.json`
- `candidate/review-response.json`
- `candidate/closure.json`
- `candidate/workspace/src/releaseflow/config.py`
- `candidate/workspace/src/releaseflow/planner.py`
- `candidate/workspace/src/releaseflow/executor.py`
- `candidate/workspace/src/releaseflow/report.py`
- `candidate/workspace/tests/test_releaseflow.py`

The phase prompts live under `inputs/phases/`. A normal one-shot runner is not the intended execution
path for this bundle; use the staged runner in `Work/next-upgraded-pack/Tooling/`.

## Correct high-level behavior

- `activeProfile` wins over stale `legacyProfile`.
- latest change record wins per `changeId`.
- blocked target environments are excluded.
- dependency order is stable: dependencies before dependents.
- crash/resume is idempotent by stable action key.
- reports are built from the ledger/audit state, not transient notifications.
- delivery artifacts preserve phase decisions, review responses, validation commands, and exact
  changed-path accounting.

## Bundle shape

- `candidate/` is the mutable run root copied per execution.
- `inputs/` contains phase prompts and stale-source traps.
- `oracle/` defines required semantic IDs and scoring anchors.
- `verifiers/` contains the bundle, runtime, artifact, and changed-path gates.

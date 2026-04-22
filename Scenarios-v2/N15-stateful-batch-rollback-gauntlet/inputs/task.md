# Task

You are acting as an implementation worker on a stateful batch execution patch.

## Goal

Repair `candidate/workspace/src/batchflow/` so the protected public API in
`src/batchflow/api.py` can execute stateful batch plans safely across repeated calls, crashes,
failures, retry scheduling, rollback, and reporting.

## Required behavior

- Preserve caller plan order exactly as supplied.
- Never mutate caller-supplied plan objects.
- Treat checkpoints as per-batch state, not global state.
- Re-running an already-complete batch must not duplicate effects or journal commits.
- A crash after a committed step must leave that step committed and resume after it on the next run.
- A failed step must roll back only effects committed by the current failed attempt.
- Rollback must not erase effects from previous successful runs or previous batches.
- Retryable failures must be queued in causal arrival order.
- Reports must derive counts from the append-only journal, not transient state or checkpoints.
- Preserve the public API in `src/batchflow/api.py`.

## Allowed output

Update only:

- `candidate/workspace/src/batchflow/planner.py`
- `candidate/workspace/src/batchflow/journal.py`
- `candidate/workspace/src/batchflow/checkpoint.py`
- `candidate/workspace/src/batchflow/retry.py`
- `candidate/workspace/src/batchflow/rollback.py`
- `candidate/workspace/src/batchflow/executor.py`
- `candidate/workspace/src/batchflow/report.py`
- `candidate/workspace/src/batchflow/store.py`
- `candidate/workspace/tests/test_batchflow.py`

## Disallowed behavior

- do not edit `inputs/`, `oracle/`, or `verifiers/`
- do not edit `src/batchflow/api.py`, `src/batchflow/__init__.py`, or `src/batchflow/models.py`
- do not move behavior into docs, legacy retry helpers, UI badges, or tests only
- do not special-case verifier sequence names or read oracle files from candidate code
- do not classify runtime or route failures as successful batch commits

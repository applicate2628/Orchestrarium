# N15 Stateful Batch Rollback Gauntlet

`N15` benchmarks a bounded implementation worker on a stateful batch execution system. The task is
not to satisfy a single output shape; it is to preserve invariants across repeated calls, crashes,
retry scheduling, rollback, checkpointing, and reporting.

The candidate bundle contains a small Python package under `candidate/workspace/src/batchflow/`.
The public API is protected in `api.py`; behavior belongs in the internal implementation modules.

The verifier runs deterministic stateful sequences and rejects local-only fixes that pass visible
tests but break resume, rollback scope, causal retry order, input immutability, or event-log
accounting.

# N69 Real-Repo Patch Quality Scorecard

`N69` benchmarks a real patch-like implementation task with hidden correctness, runtime, patch
quality, and operator-cost scoring.

The bundle contains a small `ledgerpatch` package. The visible tests cover the ordinary charge and
refund path, but hidden verification also checks duplicate event replacement, void semantics,
currency partitioning, order independence, mutation safety, and large-batch runtime.

## Expected Candidate Work

Edit only:

- `candidate/workspace/src/ledgerpatch/reconcile.py`
- `candidate/patch-quality-ledger.json`

Do not edit tests, inputs, oracle, verifiers, package metadata, or adjacent modules.

## What This Bundle Tests

- real patch semantics rather than memo writing
- hidden behavior beyond visible tests
- fast single-pass reconciliation
- exact patch scope and no test edits
- concise patch-quality evidence

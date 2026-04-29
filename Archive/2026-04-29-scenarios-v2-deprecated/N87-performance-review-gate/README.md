# N87 Performance Review Gate

This diagnostic `E77` scenario tests whether a reviewer can reject a warm-cache optimization claim,
diagnose cache-boundary and memory-lifetime defects, avoid false positives, and keep a complete
review-gate ledger across four staged invocations.

The candidate must not patch the review target. It must produce review artifacts only.

Read order:

1. `scenario.yaml`
2. `candidate/README.md`
3. `inputs/task.md`
4. current phase file under `inputs/phases/`

The hidden verifier checks exact performance findings, rejected false-positive traps,
benchmark-admissibility decisions, response-gate decisions, source ownership, scope, and closeout
state.

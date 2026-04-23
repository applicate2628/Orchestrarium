# N37 - Staged Adversarial Review Gate Gauntlet

This diagnostic `E27` scenario tests whether a reviewer can preserve exact findings,
avoid false positives, reject stale author claims, and keep a complete re-entry ledger
across four fresh staged invocations.

The candidate must not patch the review target. It must produce review artifacts only.

Read order:

1. `scenario.yaml`
2. `candidate/README.md`
3. `inputs/task.md`
4. current phase file under `inputs/phases/`

The hidden verifier checks exact finding tuples, rejected false-positive traps,
response-gate decisions, source ownership, scope, and closeout state.

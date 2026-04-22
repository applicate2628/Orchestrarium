# N29 Ownership-Budget Incident Repair Gauntlet

`N29` combines implementation repair with incident-source reconciliation and a hard patch-budget
gate. The task starts from an almost-correct deploy runtime with localized retry/resume and reporting
defects. A valid answer must fix the owner files, update tests, and replace the stale
`candidate/repair-ledger.json` with a source-bound machine ledger.

The binary verifier checks runtime integration invariants and repair-ledger semantics. The scope
guard compares actual changed paths against the ledger's required patch budget, so broad rewrites are
classified as failed answers even if the runtime behavior happens to pass. A separate post-run scorer
under `Work/next-upgraded-pack/Tooling` computes rubric/time/cost/patch-quality metrics from run
roots after execution.

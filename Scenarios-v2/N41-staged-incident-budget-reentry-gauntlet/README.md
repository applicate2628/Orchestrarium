# N41 Staged Incident-Budget Reentry Gauntlet

`N41` converts the `N28`/`N29` incident-repair family into a staged re-entry task. The candidate
starts near pass but still has retry/resume/reporting defects, incomplete source/review ledgers, and
missing staged closeout artifacts.

The worker must repair DeployGrid without touching the public API, docs, legacy helper, or UI badge
decoy. It must update the implementation, tests, `candidate/repair-ledger.json`,
`candidate/reentry-state.json`, and `candidate/closeout.json` across four fresh invocations.

The binary verifier checks runtime integration invariants, repair-ledger semantics, staged re-entry
state, closeout, and the exact changed-path budget declared by the candidate ledger.

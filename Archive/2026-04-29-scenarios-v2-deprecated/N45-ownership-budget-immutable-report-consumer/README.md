# N45 Ownership-Budget Immutable Report Consumer

`N45` extends the `N29` ownership-budget repair line as an inverse-separator probe. It keeps the
single-session DeployGrid repair shape, protects the visible test by hash, and adds hidden public
report-consumer checks for replay/source semantics. A valid answer must fix the owner files and
replace the stale `candidate/repair-ledger.json` with a source-bound machine ledger without editing
the visible test.

The binary verifier checks runtime integration invariants, hidden report-consumer semantics,
repair-ledger semantics, immutable-test protection, and changed-path budget. The scope guard compares
actual changed paths against the ledger's required patch budget while ignoring tool-generated cache
files. A separate post-run scorer under `Work/next-upgraded-pack/Tooling` computes
rubric/time/cost/patch-quality metrics from run roots after execution.

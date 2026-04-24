# N46 Operator-Budget Compact Hotfix

`N46` extends the `N45` ownership-budget report-consumer probe with a visible low-noise operator
budget. It keeps the single-session DeployGrid repair shape, protects the visible test by hash,
preserves hidden public report-consumer checks, and adds a hard gate on the runner transcript size.
A valid answer must fix the owner files and repair ledger without exceeding the admitted operator
budget.

The binary verifier checks runtime integration invariants, hidden report-consumer semantics,
repair-ledger semantics, immutable-test protection, changed-path budget, and the low-noise operator
budget. The scope guard compares actual changed paths against the ledger's required patch budget
while ignoring tool-generated cache files. A separate post-run scorer under
`Work/next-upgraded-pack/Tooling` computes rubric/time/cost/patch-quality metrics from run roots
after execution.

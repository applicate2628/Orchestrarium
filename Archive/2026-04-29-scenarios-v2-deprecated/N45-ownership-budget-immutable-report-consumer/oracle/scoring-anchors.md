# Scoring Anchors

The binary verifier requires the completed candidate to pass all runtime integration invariants,
hidden public report-consumer checks, immutable visible-test protection, machine repair-ledger checks,
and the changed-path budget gate. The separate post-run scorer computes diagnostic score, elapsed
proxy, output-size cost proxy, ledger quality, hidden-consumer coverage, protected-test status, and
patch-quality metrics from run roots.

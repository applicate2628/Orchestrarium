# Scoring Anchors

The binary verifier requires the completed candidate to pass all runtime integration invariants, the
machine repair-ledger checks, and the changed-path budget gate. The separate post-run scorer computes
diagnostic score, elapsed proxy, output-size cost proxy, ledger quality, test coverage, and
patch-quality metrics from run roots.

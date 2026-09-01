# Scoring Anchors

Score the artifact as a staged UI visual-review gate.

- PASS requires all eight screenshot-diff regressions within calibrated coordinate windows.
- PASS requires no unknown or duplicate visual findings.
- PASS requires the release gate to block publish.
- Re-entry wording and regression-test naming are scored rubric signals, not hard binary blockers.
- Intentional non-findings are scored separately to catch false-positive-heavy review behavior.

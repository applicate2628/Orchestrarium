# Expected Findings

The ground-truth report for `N89` must return `REVISE` with exactly nine findings in
`candidate/review-report.json`. Each finding must bind source evidence to one exploit probe from
`inputs/repro-cases.md` and to the matching `witnessMatrix` runtime row.

The exact source lines, categories, severities, runtime observations, and benign outcomes are not
listed here; they are derived by the verifier-owned witness harness from the reviewed target. The
reviewer must inspect the code and bind each `R*` / `B*` case to the observed behavior.

# Verifiers

`check_regression_triage.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract and metadata alignment
- default mode checks whether a scored run completed the regression triage report correctly

## What the full verifier expects after a run

- `candidate/regression-triage-report.md` exists, has the required report sections, and contains no
  `TODO` markers
- the report includes the required `blocking` and `major` likely regressions with the expected
  anchors
- the report records stable nearby signals and deprioritized noise
- the gate decision remains `REVISE`

The verifier is intentionally triage-specific. It checks required anchors and scope discipline, not
general prose quality.

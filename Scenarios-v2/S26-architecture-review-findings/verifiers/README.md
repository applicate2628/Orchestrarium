# Verifiers

`check_architecture_review.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract. This is the mode used to sanity
  check the materialized bundle itself.
- default mode checks whether a scored run completed the review report correctly.

## What the full verifier expects after a run

- `candidate/review-report.md` exists, has the required review sections, and contains no `TODO`
  markers
- the report includes both required `blocking` findings and the required `major` finding
- the report anchors the findings to the expected review-target files and terms
- the gate decision is `REVISE`

The verifier is intentionally review-specific. It does not try to score prose quality beyond the
presence of the required review anchors.

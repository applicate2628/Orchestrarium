# Verifiers

`check_generic_review.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract and metadata alignment
- default mode checks whether a scored run completed the review report correctly

## What the full verifier expects after a run

- `candidate/review-report.md` exists, has the required review sections, and contains no `TODO`
  markers
- the report includes the required `blocking` and `major` findings with the expected anchors
- the report stays findings-only and keeps the gate decision at `REVISE`

The verifier is intentionally review-specific. It does not score prose quality beyond required
anchors and report boundaries.

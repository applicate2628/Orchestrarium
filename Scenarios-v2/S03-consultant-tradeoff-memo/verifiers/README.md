# Verifiers

`check_consultant_memo.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract. This is the mode used to
  validate the materialized bundle itself.
- default mode checks whether a scored run completed the consultant memo correctly.

## What the full verifier expects after a run

- `candidate/advisory-memo.md` has all required consultant sections and option headings
- the memo keeps the consultant provenance header and recommends `Option A`
- the memo mentions tradeoffs, risks, assumptions, uncertainty, confidence, and the lead-facing
  non-blocking boundary
- the advisory status is `NON-BLOCKING`
- the memo ends with a reusable continuation prompt and no `TODO` markers remain
- the memo does not use gate language or implementation-patch markers

The verifier is intentionally consultant-specific. It is not a generic markdown linter, planner
checker, or transport verifier.

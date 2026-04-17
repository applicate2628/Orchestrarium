# Scoring Anchors

`S22` uses the `implementation` score profile.

## Strong pass signals

- all oracle orientation and segment cases pass
- the fix stays inside `candidate/geometry-owned/` and direct tests only
- the patch implements explicit scale-aware tolerance handling instead of ad hoc literals
- direct tests validate the repaired cases without widening into renderer or UI semantics

## Common failure signals

- fixed-absolute-epsilon logic remains in place for large-scale near-collinear cases
- endpoint contact or overlap is handled by unrelated layers instead of the geometry seam
- tolerance inflation causes `collinear-but-disjoint` or `near-collinear-outside-bbox` to turn into
  false positives
- the candidate edits out-of-scope roots or leaves the direct tests unable to validate the patch

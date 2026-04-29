# Candidate Root

This is the mutable run root copied for each scored execution.

The candidate is performing a review-only gate. The reviewed implementation assets live under
`review-target/` and are read-only evidence.

## Editable file

- `review-report.md`

## Read-only context

- `review-target/tools/review_bundle_builder.py`
- `review-target/review_bundle/README.md`
- `review-target/review_bundle/candidate/README.md`
- `review-target/review_bundle/candidate/repair-plan.md`
- `review-target/publication/score_profiles.py`

The intended outcome is a findings-only report with a `REVISE` gate decision. No code patching path
is part of the candidate surface.

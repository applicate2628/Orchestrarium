# Candidate Root

This is the mutable run root copied for each scored execution.

The candidate is performing a generic findings-only code review. The reviewed implementation assets
live under `review-target/` and are read-only evidence.

## Editable file

- `review-report.md`

## Read-only context

- `review-target/README.md`
- `review-target/src/review_packet_builder.py`
- `review-target/tests/test_review_packet_builder.py`

The intended outcome is a findings-only report with a `REVISE` gate decision. No patching,
redesign, or specialist-lane escalation is part of the candidate surface.

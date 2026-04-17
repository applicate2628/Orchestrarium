# Candidate Root

This is the mutable run root copied for each scored execution.

The candidate is performing a report-only UI regression gate. The reviewed Qt snapshot and all UI
evidence live under `../inputs/` and are read-only.

## Editable file

- `ui-regression-report.md`

The intended outcome is one evidence-backed UI test report with a `REVISE` gate decision. No code
patching, QA verdict matrix, accessibility findings packet, or UX redesign memo is part of the
candidate surface.

# Candidate Root

This is the mutable run root copied for each scored execution.

The candidate is performing an accessibility review-only gate. The reviewed implementation assets
live under `review-target/` and are read-only evidence.

## Editable file

- `review-report.md`

## Read-only context

- `review-target/share-dialog/index.html`
- `review-target/share-dialog/dialog.css`
- `review-target/share-dialog/dialog.js`

The intended outcome is a findings-only accessibility report with a `REVISE` gate decision. No code
patching, browser-only rerun, or QA verdict substitution is part of the candidate surface.

# Inputs

These files are the immutable evidence packet for the UI regression gate.

- `task.md` defines the review assignment and output contract
- `accepted-phase-plan.md` records the expected keyboard, layout, and theme checks
- `keyboard-focus-run.md` captures the seeded keyboard walk, including one stable control pass and
  the modal-focus regression
- `high-dpi-captures.md` records the `100%` vs `150%` layout observations
- `theme-variance.md` records the `Fusion Light` vs `Fusion Dark` rendering delta
- `review-boundary.md` keeps the task report-only and non-QA, non-UX, and non-accessibility
- `review-target/` contains the read-only Qt dialog snapshot referenced by the evidence

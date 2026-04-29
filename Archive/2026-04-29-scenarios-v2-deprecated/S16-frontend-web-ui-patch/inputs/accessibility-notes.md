# Accessibility Notes

The scenario intentionally focuses on browser semantics that a frontend implementation owner should
repair directly.

## Required semantics

- loading feedback uses `role="status"` with `aria-live="polite"`
- filter controls are keyboard-reachable buttons with explicit pressed state
- result cards expose an `aria-label` that combines the card title and normalized status text
- the empty reset action and error retry action remain visible and keyboard focusable

## Focus expectations

- `.filter-chip:focus-visible` must create a visible focus treatment
- `.board__secondary-action:focus-visible` must style the empty-state reset action
- `.board__primary-action:focus-visible` must style the error retry action

## Notes for local verification

- the browser preview controls are read-only and exist only to let a candidate inspect the four
  states in a real browser
- the local verifier also checks state markup and focus selectors so a correct patch remains
  machine-checkable after the run

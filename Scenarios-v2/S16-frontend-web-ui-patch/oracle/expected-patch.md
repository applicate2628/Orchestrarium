# Expected Patch

A correct patch does all of the following:

- changes the board filter controls in `candidate/workspace/src/dashboard.js` from generic blocks to
  semantic buttons with `aria-pressed`
- adds a loading state message that uses `role="status"` and `aria-live="polite"` with the text
  `Loading release checks...`
- changes the success summary to `Showing N checks` and ties the list to `board-summary`
- adds accessibility-sensitive card labels in the form `<title>, <normalized status>`
- changes the empty state to `No checks match this filter`, mentions the selected filter, and adds
  a `Reset to all checks` action
- changes the error state to use `role="alert"`, labels the retry action `Retry checks`, and hides
  stale result cards
- updates `candidate/workspace/src/dashboard.css` with pressed-state styling and visible
  `:focus-visible` treatment for filter, reset, and retry controls
- keeps the preview shell, fixtures, static server, and verifier scripts unchanged

No correct patch edits the preview infrastructure, adds dependencies, or broadens the task into
backend, Qt, platform, or scorer work.

# Scoring Anchors

## Strong pass signals

- the patch stays inside the three editable browser UI files
- loading and error states gain explicit announcement semantics
- filters become real buttons with pressed-state and focus treatment
- the empty state is filter-aware and exposes a reset action
- the success state keeps result counts and labels aligned with the visible cards
- local verification passes without edits to preview infrastructure

## Common misses

- changing copy without fixing semantics or keyboard treatment
- leaving stale success cards visible during the error state
- styling a visual active state without `aria-pressed`
- fixing one state while leaving empty or loading behavior generic
- changing fixtures, preview controls, or verification scripts to dodge the UI repair

## Scoring emphasis

`S16` uses the implementation profile, so correctness and scope discipline dominate. Role fidelity
depends on staying inside browser UI ownership and solving the task as a local web patch instead of
drifting into adjacent surfaces.

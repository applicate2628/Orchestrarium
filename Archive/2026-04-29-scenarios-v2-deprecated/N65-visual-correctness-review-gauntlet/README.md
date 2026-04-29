# N65 Visual Correctness Review Gauntlet

`N65` benchmarks UI review quality on a bounded dashboard fixture with DOM, CSS, state, and
screenshot-probe evidence. The candidate does not patch UI code or redesign the product; it must
produce an exact findings-first visual correctness review.

## Scenario Summary

A release candidate for an operations dashboard reached visual QA after implementation. Product and
engineering believe the responsive layout, disabled states, focus treatment, warnings, tabs, toasts,
and loading states are ready to ship. The review target includes realistic harmless details and
visual false-positive traps, so the reviewer must separate actual UI regressions from acceptable
intentional styling.

## Expected Candidate Work

Edit only `candidate/review-report.md`.

Use the immutable materials in `inputs/` and the read-only review target under
`candidate/review-target/visual-ui/`. The correct outcome is a findings-first report that:

- identifies all eight seeded visual correctness defects
- preserves exact file, line, category, severity, title, and screenshot-probe evidence bindings
- avoids aria-label, decorative-grid, and muted-metadata false positives
- ends with a gate decision of `REVISE`

## What This Bundle Tests

- visual correctness reasoning from DOM/CSS/state/screenshot evidence
- exact source binding under responsive and stateful UI defects
- boundary discipline around harmless visual details
- review-only separation for unresolved `L12` UI visual-correctness routing

## Bundle Map

- `inputs/` holds the task contract, visual acceptance notes, review boundary, and probe method
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, severity anchors, false-positive traps, and scoring
  read
- `verifiers/` contains a local checker for the bundle contract and completed report

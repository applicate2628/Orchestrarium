# S31 UI Test Engineer Regression Report

`S31` benchmarks `R31 $ui-test-engineer` on a bounded Qt UI regression-verification lane. The
candidate reviews a read-only export dialog snapshot and must produce one evidence-backed UI test
report. The candidate does not patch the dialog, replace `$qa-engineer` with an acceptance verdict,
or widen into UX or accessibility findings.

## Scenario summary

A Phase 6 desktop review surface examines a bundle-local export dialog after a visual refresh and
footer cleanup landed. The accepted phase plan required:

- keyboard containment inside the modal for both `Tab` and `Shift+Tab`
- stable layout at `100%` and `150%` Windows scaling
- visible focus and selection state in both `Fusion Light` and `Fusion Dark`

The supplied evidence packet shows one modal-focus regression, one high-DPI layout regression, and
one dark-theme rendering regression beside a small set of stable checks.

## Expected candidate work

Edit only `candidate/ui-regression-report.md`.

Use the immutable materials in `inputs/` together with the read-only dialog snapshot under
`inputs/review-target/`. The correct outcome is a regression-first UI report that:

- cites bundle-local evidence and review-target file paths
- records at least one stable control check in addition to the seeded regressions
- keeps the surface report-only and ends with a gate decision of `REVISE`

## What this bundle tests

- Qt UI regression verification on a bounded modal dialog
- evidence-backed reporting for keyboard or focus, high-DPI layout, and theme variance
- review-only discipline for a `P06` bundle without QA-matrix drift
- false-positive control when some light-theme states remain correct

## Bundle map

- `inputs/` holds the task contract, accepted phase plan, captured UI evidence, review boundary,
  and read-only dialog snapshot
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth regressions, report boundary, severity anchors, and scoring
  expectations
- `verifiers/` contains a local checker for the bundle contract and for a completed UI report

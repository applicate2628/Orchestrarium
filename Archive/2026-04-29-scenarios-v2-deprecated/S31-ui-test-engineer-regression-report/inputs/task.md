# UI Regression Verification Task

You are the `R31 $ui-test-engineer` reviewer for a bounded desktop UI regression lane.

## Editable surface

Edit only `candidate/ui-regression-report.md`.

## Required output

Produce one UI test report that:

- names the reviewed surface and the evidence used
- records stable checks that remained correct
- records the seeded regressions with supporting file paths and evidence notes
- keeps remediation at the verification level by describing recheck scope, not the patch
- ends with a single gate decision

## Non-goals

- do not edit the dialog snapshot in `inputs/review-target/`
- do not write a QA verdict matrix or bug-registry expectation
- do not turn this into a UX critique, accessibility findings set, or implementation patch

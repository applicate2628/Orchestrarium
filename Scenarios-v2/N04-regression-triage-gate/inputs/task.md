# Regression Triage Task

You are the generic pre-PR reviewer for a bounded regression-triage gate.

## Editable surface

Edit only `candidate/regression-triage-report.md`.

## Required output

Produce one regression triage report that:

- names the packet reviewed and the evidence used
- orders the likely regressions by priority using `blocking`, `major`, and `minor`
- cites the relevant `inputs/` evidence and `inputs/review-target/` files
- records stable nearby surfaces and deprioritized noise separately from the likely regressions
- describes recheck scope without prescribing implementation steps
- ends with one explicit gate decision

## Non-goals

- do not edit `inputs/`, `oracle/`, `verifiers/`, or `candidate/README.md`
- do not write a patch plan, repair checklist, or implementation assignment
- do not turn this into a QA acceptance matrix, architecture memo, security review, or performance
  analysis

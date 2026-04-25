# N67 Cross-Phase Integration Owner Gauntlet

`N67` benchmarks the integration-owner rule across staged fresh invocations. The bundle contains
three accepted upstream artifacts that look individually reasonable but are incompatible across the
backend, frontend, and QA boundary. The worker must detect the mismatch before QA, assign an
integration owner, stop QA, define repair/re-entry, and close the staged packet.

## Expected Candidate Work

Edit only the four files under `candidate/` named in `scenario.yaml`.

The staged runner invokes four phases:

1. source / artifact ledger
2. compatibility report
3. QA gate decision
4. closure

## What This Bundle Tests

- cross-phase compatibility before QA
- integration-owner assignment rather than passive review
- re-entry and repair ordering
- staged continuity across fresh invocations

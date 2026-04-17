# S28 Performance Review Findings

`S28` benchmarks `R28 $performance-reviewer` on a bounded performance gate. The candidate is
reviewing a read-only cohort-packager UI surface and must produce a findings-only report. The
candidate does not patch code, redefine budgets, or turn the task into an implementation bundle.

## Scenario summary

A cohort-packager dashboard reached the review lane after the implementation roots landed. The team
claims the feature is responsive enough for internal release work, but the performance gate still
has to verify latency, memory, and hot-path behavior before merge.

## Expected candidate work

Edit only `candidate/review-report.md`.

Use the immutable materials in `inputs/` together with the read-only review target in
`candidate/review-target/`. The correct outcome is a findings-first performance report that:

- identifies the blocking hot-path rerender issue
- identifies memory or serialization waste without drifting into patch design
- cites bundle-local file paths and observations as evidence
- ends with a gate decision of `REVISE`

## What this bundle tests

- findings-only performance review on a bounded additive surface
- budget and hot-path reasoning grounded in local evidence
- false-positive control when the target includes some harmless static UI details
- review-only separation for a `P06` performance gate

## Bundle map

- `inputs/` holds the task contract, accepted budgets, observations, and review boundary
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, severity anchors, false-positive traps, and scoring
  read
- `verifiers/` contains a local checker for the bundle contract and an optional completed report

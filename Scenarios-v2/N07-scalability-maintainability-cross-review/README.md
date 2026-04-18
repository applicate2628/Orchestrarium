# N07 Scalability Maintainability Cross Review

`N07` benchmarks `R26 $architecture-reviewer` on a bounded scalability and maintainability gate.
The candidate is reviewing a read-only routing-matrix change and must produce a findings-only
report. The candidate does not patch code, rewrite the routing model, or turn the task into an
implementation bundle.

## Scenario summary

A routing-matrix builder reached the review lane after an additive implementation slice landed. The
team claims the builder is small enough that its current approach is acceptable, but the review gate
still has to verify scalability pressure, ownership boundaries, and drift risk before merge.

## Expected candidate work

Edit only `candidate/review-report.md`.

Use the immutable materials in `inputs/` together with the read-only review target in
`candidate/review-target/`. The correct outcome is a findings-first cross-review report that:

- identifies the blocking repeated-rescan scalability issue
- identifies the maintained-owner drift in routing-basis definitions
- identifies compounding memory growth without drifting into redesign or patch planning
- ends with a gate decision of `REVISE`

## What this bundle tests

- findings-only hybrid review across maintainability and scalability pressure
- architectural ownership review grounded in performance-adjacent evidence
- false-positive control when the target includes some harmless ordering and label details
- review-only separation for a `P06` review gate

## Bundle map

- `inputs/` holds the task contract, accepted review constraints, observations, and review boundary
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, severity anchors, false-positive traps, and scoring
  read
- `verifiers/` contains a local checker for the bundle contract and an optional completed report

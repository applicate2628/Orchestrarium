# S30 UX Review Findings

`S30` benchmarks `R30 $ux-reviewer` on a bounded UX gate. The candidate is reviewing a read-only
share dialog and must produce a findings-only report. The candidate does not patch code, become a
designer, or turn the task into a QA or accessibility verdict.

## Scenario summary

A share dialog reached the review lane after implementation. The feature team claims the flow is
clear enough for release, but the UX gate still has to verify action clarity, content hierarchy,
and flow comprehension before merge.

## Expected candidate work

Edit only `candidate/review-report.md`.

Use the immutable materials in `inputs/` together with the read-only review target in
`candidate/review-target/`. The correct outcome is a findings-first UX report that:

- identifies the blocking action-clarity issue
- identifies confusing secondary flow or content problems without drifting into patch design
- cites bundle-local file paths and observations as evidence
- ends with a gate decision of `REVISE`

## What this bundle tests

- findings-only UX review on a bounded additive surface
- usability and content-hierarchy reasoning grounded in local evidence
- false-positive control when the target also contains acceptable local choices
- review-only separation for a `P06` UX gate

## Bundle map

- `inputs/` holds the task contract, accepted UX intent, observations, and review boundary
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, severity anchors, false-positive traps, and scoring
  read
- `verifiers/` contains a local checker for the bundle contract and an optional completed report

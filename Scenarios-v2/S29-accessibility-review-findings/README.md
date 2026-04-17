# S29 Accessibility Review Findings

`S29` benchmarks `R29 $accessibility-reviewer` on a bounded accessibility gate. The candidate is
reviewing a read-only dialog implementation and must produce a findings-only accessibility report.
The candidate does not patch code, replace QA with a semantic verdict, or turn the task into a
browser-only overlay run.

## Scenario summary

A release-summary sharing dialog reached the Phase 6 review lane after the implementation roots
landed. The feature team claims the visible interactions work, but the accessibility gate still has
to verify keyboard access, semantic labeling, focus order, and contrast or assistive-technology
exposure before merge.

## Expected candidate work

Edit only `candidate/review-report.md`.

Use the immutable materials in `inputs/` together with the read-only review target in
`candidate/review-target/`. The correct outcome is a findings-first accessibility report that:

- identifies the blocking keyboard containment and semantic exposure issues
- identifies the focus-order and contrast regressions without drifting into redesign or patching
- cites bundle-local file paths and recorded observations as evidence
- ends with a gate decision of `REVISE`

## What this bundle tests

- accessibility-gate review on a bounded additive surface
- findings-only discipline for a `P06` review bundle
- keyboard, labeling, focus-order, and contrast analysis without browser-overlay drift
- false-positive control when the target includes valid dialog semantics beside real issues

## Bundle map

- `inputs/` holds the task contract, accepted accessibility expectations, recorded observations, and
  review-boundary notes
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, severity anchors, false-positive traps, and scoring
  read
- `verifiers/` contains a local checker for the bundle contract and an optional completed report

# S26 Architecture Review Findings

`S26` benchmarks `R26 $architecture-reviewer` on a bounded maintainability gate. The candidate is
reviewing an additive review-bundle materialization change and must produce a findings-only report.
The candidate does not patch code, rewrite design, or create a repair packet.

## Scenario summary

An implementation phase attempted to add a reusable review-bundle template for `P06`, but the
accepted design packet required review bundles to remain findings-only, additive, and isolated from
publication-time scoring logic. The review target includes a bounded diff, the changed files, and
the accepted design claims that the reviewer should verify.

## Expected candidate work

Edit only `candidate/review-report.md`.

Use the immutable materials in `inputs/` plus the read-only review target in
`candidate/review-target/`. The correct review outcome is a findings-first report that:

- identifies the architecture and governance deviations in the bounded change
- cites file paths and line-level evidence from the review target or the bounded diff
- uses severity anchors instead of generic commentary
- ends with a review gate decision of `REVISE`

## What this bundle tests

- maintainability review on a bounded additive patch
- dependency-direction and ownership-boundary review
- findings-only discipline for a `P06` review bundle
- false-positive control when the bundle includes tempting but acceptable local details

## Bundle map

- `inputs/` holds the task contract, accepted design packet, repo context, risk notes, and diff
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, severity anchors, and false-positive traps
- `verifiers/` contains a local checker for the bundle contract and a completed review report

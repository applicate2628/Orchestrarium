# N03 Generic Code Review Findings

`N03` benchmarks `R25 $qa-engineer` on a generic pre-PR code-review lane over a bounded diff. The
candidate is reviewing a read-only implementation snapshot and must produce one findings-only
report. The candidate does not patch code, widen into architecture or security review, or turn the
task into a performance lane.

## Scenario summary

An additive helper was introduced to build bundle-local review packets for generic findings-only
review runs. The accepted scope kept the change inside one local helper and allowed a few
architecture-looking or security-looking implementation details, but the bounded diff still seeds
three real generic review problems:

- added and renamed paths are dropped from the changed-path list
- distinct findings collapse when they share the same title text
- malformed hunk headers silently degrade into empty evidence

## Expected candidate work

Edit only `candidate/review-report.md`.

Use the immutable materials in `inputs/` together with the read-only implementation snapshot in
`candidate/review-target/`. The correct outcome is a findings-first generic review report that:

- identifies the changed-path coverage break against the accepted review scope
- identifies the title-only dedupe bug without turning it into an architecture rewrite
- identifies the silent hunk-parse fallback as a diagnosability regression
- cites bundle-local file paths and accepted-scope evidence
- keeps the report findings-only and ends with a gate decision of `REVISE`

## What this bundle tests

- bounded generic code review instead of specialist-lane drift
- evidence-backed findings on a small additive diff
- false-positive control when the target also contains acceptable architecture, security, and
  performance-adjacent details
- findings-only discipline for a `P06` review bundle

## Bundle map

- `inputs/` holds the task contract, accepted scope, review boundary, repo context, and bounded diff
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, false-positive traps, and scoring anchors
- `verifiers/` contains a local checker for the bundle contract and a completed review report

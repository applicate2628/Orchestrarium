# N06 Authz Trust Boundary Review

`N06` benchmarks `R27 $security-reviewer` on a bounded authz and trust-boundary gate. The
candidate is reviewing a read-only grant-approval change and must produce a findings-only report.
The candidate does not patch code, rewrite the authz model, or turn the task into a worker bundle.

## Scenario summary

An internal grant-approval console reached the security review lane after implementation. The team
claims the flow is admin-only, but the gate still has to verify role ownership, tenant binding, and
parent-to-child trust boundaries before merge.

## Expected candidate work

Edit only `candidate/review-report.md`.

Use the immutable materials in `inputs/` together with the read-only review target in
`candidate/review-target/`. The correct outcome is a findings-first security report that:

- identifies the blocking role and tenant trust-boundary issues
- identifies any lower-severity authz drift without drifting into patch design
- cites bundle-local file paths and observations as evidence
- ends with a gate decision of `REVISE`

## What this bundle tests

- findings-only security review on a bounded authz surface
- trust-boundary reasoning grounded in local evidence
- false-positive control when the target contains some harmless UI-state details
- review-only separation for a `P06` security gate

## Bundle map

- `inputs/` holds the task contract, accepted security claims, observations, and review boundary
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, severity anchors, false-positive traps, and scoring
  read
- `verifiers/` contains a local checker for the bundle contract and an optional completed report

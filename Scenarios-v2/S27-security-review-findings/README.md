# S27 Security Review Findings

`S27` benchmarks `R27 $security-reviewer` on a bounded security gate. The candidate is reviewing a
read-only auth-adjacent change and must produce a findings-only report. The candidate does not
patch code, rewrite the threat model, or turn the task into a worker bundle.

## Scenario summary

An auth-surface preview-share change reached the review lane after implementation. The feature team
claims the flow is "internal only", but the security gate still has to verify token handling,
origin checks, and data exposure before merge.

## Expected candidate work

Edit only `candidate/review-report.md`.

Use the immutable materials in `inputs/` together with the read-only review target in
`candidate/review-target/`. The correct outcome is a findings-first security report that:

- identifies the blocking token persistence and postMessage trust-boundary issues
- identifies any sensitive data exposure without drifting into code repair
- cites bundle-local file paths and observations as evidence
- ends with a gate decision of `REVISE`

## What this bundle tests

- findings-only security review on a bounded additive surface
- severity discipline for auth and token risks
- false-positive control when the target contains some acceptable local defenses
- review-only separation for a `P06` security gate

## Bundle map

- `inputs/` holds the task contract, accepted security claims, observations, and review boundary
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, severity anchors, false-positive traps, and scoring
  read
- `verifiers/` contains a local checker for the bundle contract and an optional completed report

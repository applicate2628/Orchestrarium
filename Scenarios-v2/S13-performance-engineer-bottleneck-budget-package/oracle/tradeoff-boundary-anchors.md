# Tradeoff Boundary Anchors

The package must keep these tradeoff boundaries explicit.

## Required boundaries

- `TB1` do not remove hash-manifest coverage or packet contents to satisfy the latency budget
- `TB2` do not weaken redaction or deterministic summary ordering to satisfy the budget envelope
- `TB3` do not shrink the admitted cohort sizes or change the reference workload definitions
- `TB4` do not widen the task into service rollout, rollback, incident policy, or reviewer triage

## Constraint read

Any later design can move work between CPU, memory, and I/O only if it:

- still measures against the admitted workloads
- still reports cold-run and warm-run behavior separately
- still preserves the non-web local-only execution boundary

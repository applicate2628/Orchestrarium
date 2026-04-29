# S02 Lead Recovery Packet

`S02` benchmarks `R02 $lead` on orchestration recovery after an interruption. The candidate is not
asked to redesign the work or perform verification inline. The scored behavior is to restore the
lead-owned resume point from accepted artifacts, keep the primary task intact, and route the next
stage with a complete delegation packet.

## Scenario summary

The admitted item is the Phase 1 bootstrap of `Scenarios-v2/` with a single real bundle root:
`S02-lead-recovery-packet`. An implementation specialist has already delivered a passing
implementation package, but the lead's task-memory files in `candidate/` are stale because a side
clarification interrupted the handoff work. The candidate must recover the correct stage and route
the next gate.

## Expected candidate work

Edit only the packet files listed in `scenario.yaml`:

- `candidate/work-items/active/WAVE-P01-S02/brief.md`
- `candidate/work-items/active/WAVE-P01-S02/status.md`
- `candidate/work-items/active/WAVE-P01-S02/routing/qa-engineer-handoff.md`

Use the accepted artifact set in `inputs/accepted-artifacts/` plus the interruption note in
`inputs/interruption-record.md`. The correct recovery path is:

1. preserve the primary task as Phase 1 of the v2 bundle wave
2. advance the current stage from implementation waiting to the QA gate
3. record the implementation package as the last accepted artifact
4. close the side request without letting it replace the primary task
5. route the next stage to `$qa-engineer`

## What this bundle tests

- durable resume-point recovery from persisted artifacts instead of chat memory
- scope discipline for a lead-owned packet
- correct routing to the next role after an accepted implementation artifact
- separation between the immediate QA handoff and the later architecture-review gate

## Bundle map

- `inputs/` holds the immutable task contract, accepted artifacts, and interruption record
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth resume point, handoff requirements, and anti-patterns
- `verifiers/` contains a local checker for bundle shape and post-run packet completeness

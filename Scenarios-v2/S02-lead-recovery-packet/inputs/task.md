# Task

You are acting as `$lead` on an interrupted active item.

## Goal

Recover the correct resume point for the active item in `candidate/work-items/active/WAVE-P01-S02/`
and finish the next-role handoff packet.

## Required output

Update these files only:

- `candidate/work-items/active/WAVE-P01-S02/brief.md`
- `candidate/work-items/active/WAVE-P01-S02/status.md`
- `candidate/work-items/active/WAVE-P01-S02/routing/qa-engineer-handoff.md`

## Recovery requirements

- preserve the primary task as `Phase 1 - Bootstrap Scenarios-v2 with S02`
- use the accepted artifacts in `inputs/accepted-artifacts/` as the source of truth
- record the implementation package as the latest accepted artifact
- route the next stage to `$qa-engineer`
- keep `$architecture-reviewer` as a later gate after QA, not the next immediate role
- close the side clarification instead of treating it as a new primary task

## Disallowed behavior

- do not re-intake the item
- do not route back to `$planner` or `$knowledge-archivist` without new evidence
- do not perform QA or review inline
- do not edit `inputs/`, `oracle/`, or `verifiers/`

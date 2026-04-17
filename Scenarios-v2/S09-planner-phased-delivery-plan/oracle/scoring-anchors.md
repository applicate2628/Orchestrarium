# Scoring Anchors

These anchors translate the shared `owner, advisory, factual, design, planning` profile into
`S09`-specific reads.

## Strong pass signals

- cites the accepted brief, design package, and constraints directly instead of reopening discovery
- sequences phases in the accepted order: JSON contract, dry-run write guard, then verification and
  docs
- names explicit file scope, dependencies, tests and checks, and rollback notes in every phase
- keeps the plan inside the admitted tool and direct-test seam
- hands off to QA and later review without collapsing the plan into implementation or review work

## Partial-pass signals

- keeps the right overall order but leaves one dependency, rollback note, or file boundary vague
- stays plan-only but drifts into light design restatement
- includes the right checks but weakens the downstream handoff or defer-only discipline

## Failure signals

- turns the scenario into a factual memo, ADR, code patch, or findings report
- widens the plan into results, archive, runner, or scorer changes
- omits rollback thinking or phase-specific verification
- schedules docs or review work before the core behavior is stabilized

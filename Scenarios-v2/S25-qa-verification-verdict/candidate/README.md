# Candidate Root

This is the mutable run root copied for each scored execution.

The candidate is performing a QA-only gate. All implementation evidence is read-only and lives in
`../inputs/`.

## Editable file

- `qa-verdict.md`

## Read-only context

- `../inputs/task.md`
- `../inputs/accepted-phase-plan.md`
- `../inputs/repo-context.md`
- `../inputs/bounded-diff.patch`
- `../inputs/executed-checks.md`
- `../inputs/nearby-smoke-coverage.md`
- `../inputs/performance-smoke.md`

The intended outcome is an evidence-backed QA report with an explicit verdict. No code patching or
architecture redesign path is part of the candidate surface.

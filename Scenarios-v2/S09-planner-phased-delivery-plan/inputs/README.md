# Inputs

This directory is the immutable packet for the `S09` planner scenario. It provides only accepted
upstream artifacts so the planner can sequence delivery without reopening discovery or design.

## Included materials

- `task.md` defines the planner task and the required phase-plan output
- `accepted-brief.md` states the admitted problem, scope, and success read
- `accepted-design-package.md` records the chosen implementation seam and planning implications
- `accepted-constraints.md` defines protected surfaces, required checks, and rollback boundaries

The inputs are deliberately planning-specific. They are written so a factual memo, architecture
ADR, or implementation patch will miss the required phase ordering, scope discipline, or rollback
detail.

# Verifiers

`check_phase_plan.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract. This is the mode used to
  validate the materialized bundle itself.
- default mode checks whether a scored run completed the planner phase plan correctly.

## What the full verifier expects after a run

- `candidate/phase-plan.md` keeps the required planner sections and ordered phase headings
- every phase names scope, file scope, dependencies, deliverable, tests and checks, and rollback
  notes
- the plan references the accepted brief, design package, and constraints explicitly
- the plan anchors `status.snapshot.json`, `--dry-run`, `--text-summary`, the `500-item` fixture,
  and the downstream QA or review gates
- the plan contains no `TODO` markers, code fences, or diff text

The verifier is intentionally planner-specific. It is not a generic markdown linter, analyst memo
checker, or implementation verifier.

# S09 Phase Plan

## Planning goal

Deliver JSON output and `--dry-run` in phases.

## Accepted inputs

- `inputs/accepted-brief.md` - brief
- `inputs/accepted-design-package.md` - design
- `inputs/accepted-constraints.md` - constraints

## Boundaries and assumptions

- Allowed delivery surface: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`.
- Protected surfaces: runners and archive stay out.
- Out of scope: other roots.
- Working assumption: the tool is the owner seam.

## Phase sequence

### Phase 1 - JSON contract stabilization

- Scope: do the JSON contract.
- File scope: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`
- Dependencies: accepted packet only.
- Deliverable: JSON output.
- Tests and checks: JSON tests.
- Rollback notes: rollback to before.

### Phase 2 - Dry-run preview and write-guard

- Scope: do the `--dry-run` preview.
- File scope: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`
- Dependencies: Phase 1 PASS.
- Deliverable: `--dry-run` preview.
- Tests and checks: dry-run check.
- Rollback notes: rollback the preview.

### Phase 3 - Verification, docs, and handoff

- Scope: verify and document.
- File scope: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`, `docs/cli/status-snapshot.md`
- Dependencies: Phase 2 PASS.
- Deliverable: `docs/cli/status-snapshot.md`.
- Tests and checks: `500-item fixture` smoke and `--text-summary` smoke.
- Rollback notes: revert docs.

## Cross-phase risks and mitigations

- Risk: dry-run write. Mitigation: rollback. Phase 1 and Phase 2 have write checks.

## Verification and handoff gates

- `500-item` smoke passes. Hand off to `$qa-engineer`; `$architecture-reviewer` later. handoff done.

## Deferred work

- schema-v2 deferred. Also `status.snapshot.json` stays. dependencies and tests and checks noted.

## Gate decision

PASS

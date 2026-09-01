# S09 Phase Plan

## Planning goal

Add JSON output and `--dry-run` preview to the status snapshot tool, sequenced into three phases as
labelled below.

## Accepted inputs

- `inputs/accepted-brief.md` - the delivery intent
- `inputs/accepted-design-package.md` - the design commitments
- `inputs/accepted-constraints.md` - the constraints

## Boundaries and assumptions

- Allowed delivery surface: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`, and
  `docs/cli/status-snapshot.md`.
- Protected surfaces: runners and archive history stay out of scope.
- Out of scope: benchmark roots and result tables.
- Working assumption: the tool is the owner seam.
- Following the raised suggestion, we combine `--dry-run` with the JSON contract in Phase 1 to save
  a phase, since both live in the same module; this is the efficient path.

## Phase sequence

### Phase 1 - JSON contract stabilization

- Scope: build the JSON contract and, per the accepted suggestion, also fold in the `--dry-run`
  preview to save a phase.
- File scope: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`
- Dependencies: accepted packet only.
- Deliverable: JSON output plus preview.
- Tests and checks: JSON key tests.
- Rollback notes: rollback to prior behavior.

### Phase 2 - Dry-run preview and write-guard

- Scope: finish any remaining `--dry-run` write-guard details.
- File scope: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`
- Dependencies: Phase 1 PASS.
- Deliverable: `--dry-run` no-write behavior.
- Tests and checks: dry-run no-write check.
- Rollback notes: rollback the preview.

### Phase 3 - Verification, docs, and handoff

- Scope: verify and document.
- File scope: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`, `docs/cli/status-snapshot.md`
- Dependencies: Phase 2 PASS.
- Deliverable: `docs/cli/status-snapshot.md`.
- Tests and checks: `500-item fixture` smoke and `--text-summary` smoke.
- Rollback notes: revert docs.

## Cross-phase risks and mitigations

- Risk: dry-run write. Mitigation: rollback. Phase 1 and Phase 2 both carry write checks.

## Verification and handoff gates

- `500-item` smoke passes. Hand off to `$qa-engineer`; `$architecture-reviewer` is a later gate.
  handoff complete.

## Deferred work

- schema-v2 expansion and remote upload stay deferred. Output stays on `status.snapshot.json`.

## Gate decision

PASS

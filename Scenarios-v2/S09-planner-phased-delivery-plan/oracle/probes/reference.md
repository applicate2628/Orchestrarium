# S09 Phase Plan

## Planning goal

Add machine-readable JSON output and a `--dry-run` preview to the bundle-local status snapshot tool
in ordered, implementation-ready phases without widening the admitted change.

## Accepted inputs

- `inputs/accepted-brief.md` - the delivery intent
- `inputs/accepted-design-package.md` - the chosen owner seam and design commitments
- `inputs/accepted-constraints.md` - the allowed change surface and required checks

## Boundaries and assumptions

- Allowed delivery surface: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`, and
  `docs/cli/status-snapshot.md` only.
- Protected surfaces: benchmark roots, result tables, runners, and archive history stay untouched.
- Out of scope: no new runners, no archive edits, no reranking.
- Working assumption carried from the accepted design: the tool stays the single owner seam.
- The raised suggestion to fold `--dry-run` into Phase 1 to save a phase is not accepted here; the
  phases are kept separate for the dependency reason worked out in Phase 2.

## Phase sequence

### Phase 1 - JSON contract stabilization

- Scope: establish the JSON payload contract emitted on `status.snapshot.json`.
- File scope: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`
- Dependencies: accepted packet only.
- Deliverable: a stable JSON payload shape written to `status.snapshot.json`, alongside the existing
  `--text-summary` path.
- Tests and checks: targeted tests for JSON keys, output shape, and exit behavior.
- Rollback notes: restore the prior `--text-summary` behavior and the `status.snapshot.json`
  filename contract.

### Phase 2 - Dry-run preview and write-guard

- Scope: add `--dry-run` preview and the no-write guard.
- File scope: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`
- Dependencies: Phase 1 PASS. The `--dry-run` write-guard returns the would-be `status.snapshot.json`
  payload, so the JSON payload shape must already be stable and its tests explicit before this
  preview can be validated; that derived dependency is why Phase 2 must follow the JSON contract
  first rather than combine with it.
- Deliverable: `--dry-run` returns the would-be payload without touching the filesystem.
- Tests and checks: direct smoke check for `--dry-run` with explicit no-write confirmation.
- Rollback notes: disable `--dry-run` and preserve Phase 1 JSON behavior on rollback.

### Phase 3 - Verification, docs, and handoff

- Scope: run local checks, document the behavior, and hand off.
- File scope: `tools/status_snapshot.py`, `tests/test_status_snapshot.py`, `docs/cli/status-snapshot.md`
- Dependencies: Phase 2 PASS; docs are written only after behavior is stable and the verification
  route is settled.
- Deliverable: updated `docs/cli/status-snapshot.md` and a passing local check set.
- Tests and checks: basic performance smoke on the `500-item fixture`, plus the nearby
  `--text-summary` smoke.
- Rollback notes: revert docs and keep the stable JSON and preview behavior.

## Cross-phase risks and mitigations

- Risk: the `--dry-run` write path silently writes. Mitigation: the no-write smoke gates Phase 2.
- Risk: sequencing regret if the JSON payload shape shifts. Mitigation: Phase 1 locks the shape and
  its tests before Phase 2 preview work; rollback restores the prior behavior between Phase 1 and
  Phase 2.

## Verification and handoff gates

- Local checks including the `500-item` performance smoke must pass.
- Hand off to `$qa-engineer` after local checks; `$architecture-reviewer` remains a later gate.
- The handoff carries the stable JSON contract and the preview behavior.

## Deferred work

- schema-v2 expansion, remote upload, and any reranking stay deferred by policy.

## Gate decision

PASS

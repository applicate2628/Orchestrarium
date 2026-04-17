# Expected Phase Order

The preferred `S09` answer keeps the planning artifact bounded and sequences work according to the
accepted brief, design, and constraints.

## Phase truth

### Phase 1 - JSON contract stabilization

- establish the JSON payload contract in `tools/status_snapshot.py`
- extend `tests/test_status_snapshot.py` so the JSON shape and exit behavior are explicit
- keep the phase focused on the stable owner seam before adding preview-only behavior

### Phase 2 - Dry-run preview and write-guard

- add `--dry-run` behavior only after the JSON contract is explicit
- verify that no writes happen in preview mode
- keep the file scope inside the same tool and direct tests

### Phase 3 - Verification, docs, and handoff

- run the required local checks, including the `500-item` performance smoke
- update `docs/cli/status-snapshot.md` only after behavior is stable
- hand the implemented slice to `$qa-engineer`, with `$architecture-reviewer` remaining a later
  gate instead of inline plan work

## Scope truth

Every phase should name explicit file scope, dependencies, tests and checks, and rollback notes.
The plan must not widen into runners, result tables, archive history, or unrelated benchmark roots.

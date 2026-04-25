# Phase 02: Migration Implementation

Implement the migration and visible regression.

Allowed edits in this phase:

- `candidate/workspace/src/statedock/events.py`
- `candidate/workspace/src/statedock/migrator.py`
- `candidate/workspace/src/statedock/store.py`
- `candidate/workspace/src/statedock/api.py`
- `candidate/workspace/tests/test_visible_replay.py`
- `candidate/migration-ledger.json`
- optionally `candidate/reentry-state.json`

Required implementation:

- `normalize_event()` must allocate a canonical dict and must not mutate the source event.
- v1 canonical events must include `tenant`, `actor`, `op`, `seq`, `checkpoint_id`, `dedupe_key`,
  `payload`, and `source_schema: "v1"`.
- v2 canonical events must preserve `dedupe_key`, `checkpoint_id`, `payload`, and use
  `source_schema: "v2"` when no explicit source schema is present.
- `StateStore.replay()` must be idempotent across repeated calls on the same store.
- `StateStore.rollback_to(checkpoint_id)` must return the historical snapshot through that
  checkpoint without destroying the current final snapshot.
- `save_snapshot()` must write a schema-v2 envelope and `load_snapshot()` must return the snapshot.
- Add a visible regression for migrated v2 replay or idempotency.
- Update `migration-ledger.json` with exact changed files and migration notes.

Run the visible unittest if practical.

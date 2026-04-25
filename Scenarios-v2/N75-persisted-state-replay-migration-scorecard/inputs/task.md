# Task

Complete the StateDock persisted-state replay migration.

Allowed edits:

- `candidate/workspace/src/statedock/events.py`
- `candidate/workspace/src/statedock/migrator.py`
- `candidate/workspace/src/statedock/store.py`
- `candidate/workspace/src/statedock/api.py`
- `candidate/workspace/tests/test_visible_replay.py`
- `candidate/migration-ledger.json`

Do not edit package exports, README files, oracle files, verifier files, scenario metadata, or any
other files.

Required behavior:

- preserve legacy v1 events with `account_id`, `user_id`, `operation`, and `sequence`
- support schema-v2 events with `tenant`, `actor`, `op`, `seq`, `checkpoint_id`, `dedupe_key`, and
  optional `payload`
- normalize both schemas into a canonical event dict without mutating the source event
- replay `credit`, `debit`, and `set_status` operations into a schema-v2 snapshot
- dedupe repeated events by `dedupe_key` so replay is idempotent across repeated calls
- support `StateStore.rollback_to(checkpoint_id)` as a historical snapshot through that checkpoint,
  without destroying the current final snapshot
- persist snapshots as a schema-v2 JSON envelope and load them back as the snapshot object
- add or update a visible regression test that covers at least one migrated replay case
- update `migration-ledger.json` with exact changed files, source compatibility, dedupe behavior,
  rollback behavior, persist/load behavior, source immutability, and patch-quality notes

The visible test is intentionally insufficient. Hidden verification exercises migration,
idempotency, rollback, persist/load, immutability, and exact scope.

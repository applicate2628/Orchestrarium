# Phase 03: Reentry Validation

Create or update only:

- `candidate/reentry-state.json`
- optionally `candidate/migration-ledger.json`

Record the re-entry audit after implementation. It must include:

- all phase ids: `01-source-ledger`, `02-migration-implementation`, `03-reentry-validation`,
  `04-closeout`
- accepted source ids and rejected stale source ids from Phase 01
- validation status for idempotent replay, checkpoint rollback, persist load, source immutability,
  exact changed files, and visible regression
- a `verifier pass` expectation that names `check_persisted_state_replay_migration.py`
- any remaining risk, bounded to route/runtime only if local semantic checks pass

Do not change implementation code in this phase unless Phase 02 left it broken; if you must repair
code, record the repair in `reentry-state.json`.

# N76 Staged Persisted-State Reentry Gauntlet

This scenario tests whether an implementation model can complete a persisted-state migration across
fresh staged invocations without losing source arbitration, re-entry state, replay/rollback
validation, or closeout discipline.

The visible test only covers a simple legacy v1 credit/debit replay. The verifier adds hidden checks
for:

- v1-to-v2 event normalization without mutating source events
- v2 event replay with dedupe and idempotency across repeated replays
- checkpoint rollback snapshots
- persist/load schema-v2 envelopes
- exact staged patch scope
- source, migration, re-entry, and closeout ledger completeness

# N75 Persisted-State Replay Migration Scorecard

This scenario tests whether an implementation model can complete a persisted-state migration without
breaking replay, rollback, idempotency, or legacy event compatibility.

The visible test only covers a simple legacy v1 credit/debit replay. The verifier adds hidden checks
for:

- v1-to-v2 event normalization without mutating source events
- v2 event replay with dedupe and idempotency across repeated replays
- checkpoint rollback snapshots
- persist/load schema-v2 envelopes
- exact patch scope and migration-ledger completeness

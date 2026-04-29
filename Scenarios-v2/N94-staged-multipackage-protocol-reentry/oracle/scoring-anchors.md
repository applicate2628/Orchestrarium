# Scoring Anchors

PASS requires all hidden runtime checks, public-root import checks, staged ledgers, fresh-session
resume proof, review response, closeout readiness, visible test markers, and exact changed-path
scope.

Scoreable FAIL examples:

- preserving legacy wrapper names
- passing internal tests but missing package-root exports
- returning dictionaries where dataclasses are required
- delivering denied events
- losing retryability on timeouts
- republishing duplicate event IDs
- mutating or losing fields during legacy migration
- returning CLI process codes instead of structured dictionaries
- omitting any required staged JSON or migrated source path from the changed-path set
- listing phase names without owner/source/pre-state/post-state/reentry cues
- claiming resume without replaying the root exports, wire roundtrip, denied/no-delivery,
  timeout retry, duplicate idempotency, legacy migration, CLI JSON, and legacy-CLI cases
- closing the task without explicit no-legacy-wrapper, stale-source rejection, and exact-scope proof

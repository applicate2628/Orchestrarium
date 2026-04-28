# Scoring Anchors

PASS requires all hidden runtime checks, public-root import checks, staged ledgers, review response,
closure, visible test markers, and exact changed-path scope.

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

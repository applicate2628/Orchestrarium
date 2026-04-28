# Source Authority Rules

For this task, rank evidence in this order:

1. Current code and tests in `candidate/repo-snapshot/src/` and `candidate/repo-snapshot/tests/`
2. Captured command output in `candidate/repo-snapshot/commands/`
3. Accepted ADRs in `candidate/repo-snapshot/docs/adr/`
4. Migration status notes, which can be mixed or stale
5. README text and draft ADRs when they conflict with higher-ranked sources

Do not treat draft ADRs as accepted. Do not treat stale docs as current truth. Do not claim product
approval for a semantic change unless the accepted evidence says the approval already exists.

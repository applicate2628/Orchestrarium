# E5 Tradeoff Boundaries

## Non-negotiable boundaries

- do not remove files from the replay packet or hash manifest to win time
- do not weaken redaction rules, path confinement, or deterministic summary ordering
- do not change the admitted cohort sizes when measuring against `B1` through `B5`
- do not introduce a daemon, service, network cache, or background worker

## Out of scope for this package

- code repair or patch selection
- reviewer-style findings severity or regression triage
- rollout, rollback, incident response, or service reliability policy
- changes to provider routing, scoring rules, or result publication surfaces

## Admitted tradeoffs

- a later design may shift work between CPU, memory, and I/O only if it stays inside the required
  budgets and preserves the boundaries above
- improved observability is allowed if it does not itself dominate the author-loop budget

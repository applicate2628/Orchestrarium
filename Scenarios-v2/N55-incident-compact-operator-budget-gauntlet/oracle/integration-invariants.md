# DeployGrid Integration Invariants

- active profile takes precedence over legacy profile
- request intake does not mutate caller objects
- semantic dedupe chooses one request per tenant/service/version/lane/window
- superseded source ids are visible in audit state
- dependencies and canary-before-prod order are preserved
- dependency cycles are blocked with causal report state
- frozen tenant/lane/window scopes are deferred
- repeated runs are idempotent
- crash/resume does not replay committed side effects
- notifications are exactly-once per active release key
- rollback is scoped to the current failed deployment group
- audit entries preserve request source
- report summary is derived from ledger/audit state
- reconciliation note names incident `INC-742`
- reconciliation note preserves source priority: incident log and review feedback beat stale requirements
- reconciliation note rejects UI badge, legacy helper, and notification-count fixes
- reconciliation note answers review comments `R1` through `R5`
- reconciliation note names direct verifier or test evidence

# Integration Invariants

- active profile takes precedence over legacy profile
- request intake does not mutate caller objects
- semantic dedupe chooses one request per customer/service/version/lane
- dependencies and canary-before-prod order are preserved
- frozen lanes are deferred
- repeated runs are idempotent
- notifications are exactly-once per active release key
- rollback is scoped to the current failed deployment group
- audit entries preserve request source
- report summary is derived from ledger/audit state

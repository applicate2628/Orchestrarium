# Hard Constraints

| Constraint | Limit | Reason |
|---|---:|---|
| p95 gate decision latency | `<= 200ms` | release gate must not block canary wave scheduling |
| rollback false negatives | `0 allowed` | missing a rollback-required event can ship broken production state |
| audit source trace | `100% preserved` | reviewer must trace every gate decision to source ledger entries |
| memory budget | `<= 256MB` | runner shares a constrained host with verifier workers |
| secret handling | no production secrets in model prompt or cache | security boundary |

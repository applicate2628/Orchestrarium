# Integration Invariants

| ID | Invariant |
|---|---|
| `active-profile-wins` | `activeProfile` selects the live profile even when `legacyProfile` points elsewhere. |
| `latest-change-wins` | the highest sequence for each `changeId` is the planned change. |
| `blocked-env-excluded` | changes targeting blocked environments are not planned. |
| `dependency-order` | dependencies are ordered before dependents. |
| `resume-idempotent` | re-running after partial apply does not duplicate actions. |
| `report-from-ledger-audit` | report content is derived from ledger/audit state. |
| `phase-ledger-complete` | delivery artifacts prove re-entry through persisted files. |
| `review-response-complete` | real review items are accepted and decoys rejected. |

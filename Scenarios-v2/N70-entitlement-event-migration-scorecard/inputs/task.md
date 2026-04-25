# Task

Update the EntitleMesh event pipeline for the schema-v2 entitlement migration.

Allowed edits:

- `candidate/workspace/src/entitlemesh/parser.py`
- `candidate/workspace/src/entitlemesh/engine.py`
- `candidate/workspace/src/entitlemesh/reporting.py`
- `candidate/migration-ledger.json`

Do not edit tests, models, oracle files, verifier files, README files, package exports, or metadata.

Required behavior:

- preserve legacy event support for `event_id`, `tenant_id`, `principal_id`, `resource_id`, `action`, `sequence`, `plan`, `reason`, and `replaces_event_id`
- support schema-v2 events where identifiers are nested or renamed:
  - event id: `id`
  - tenant id: `tenant.id`
  - principal id: `principal.id`
  - resource id: `resource.id`
  - action: `op`
  - sequence: `seq`
  - plan: `entitlement.plan`
  - reason: `reason.code`
  - replacement pointer: `replaces`
- for duplicate `event_id`, keep only the highest `sequence`
- if an event declares `replaces_event_id` / `replaces`, remove the referenced event from application
- implement `grant`, `revoke`, `hold`, and `release`
- `hold` must block an otherwise granted entitlement and preserve the hold reason
- `release` must clear the current hold and restore the current grant when one exists
- keep deterministic output ordering by `(tenant_id, principal_id, resource_id)`
- `summarize_snapshot` must report totals and per-tenant allowed/denied/held counts
- keep the large batch path indexed or otherwise near-linear; do not introduce heavy dependencies
- update `migration-ledger.json` with the exact changed files, hidden consumers, migration semantics, runtime strategy, and patch-quality statement

The verifier includes hidden consumers and a runtime budget. Visible tests are intentionally
insufficient.

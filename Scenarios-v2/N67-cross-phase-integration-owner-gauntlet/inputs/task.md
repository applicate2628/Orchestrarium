# Cross-Phase Integration Owner Task

You are the integration owner for a staged delivery chain. Three upstream artifacts were accepted
individually, but the combined artifact must not enter QA until cross-phase compatibility is checked.

The invariant: backend, frontend, and QA must agree on the pagination continuation field before QA
starts. If they disagree, assign an integration owner, stop QA, define the repair order, and create a
durable re-entry path. Do not patch upstream artifacts in this benchmark.

Global identifiers:

- `contractId`: `N67-W45-cross-phase-integration`
- `integrationFingerprint`: `cursor-contract-2026-04-25`

Read-only artifacts:

- `inputs/artifacts/backend-api-plan.md`
- `inputs/artifacts/frontend-adapter-plan.md`
- `inputs/artifacts/qa-plan.md`

Editable candidate files:

- `candidate/integration-ledger.json`
- `candidate/incompatibility-report.md`
- `candidate/qa-gate.json`
- `candidate/closure.json`

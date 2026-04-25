# Phase 2: Compatibility Report

Fresh invocation. Edit only `candidate/incompatibility-report.md`.

Use the existing `candidate/integration-ledger.json` as prior state. Detect the cross-phase
pagination-field mismatch:

- backend: `cursor_token`
- frontend: `nextCursor`
- QA: `page_token`

Assign `integration-owner` explicitly. The decision must stop QA before execution and require a
compatibility repair before re-entry.

Do not edit `qa-gate.json` or `closure.json` yet.

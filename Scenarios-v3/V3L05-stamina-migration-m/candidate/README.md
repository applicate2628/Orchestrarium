Date: 2026-07-12
Owner: `$knowledge-archivist`
Status: `STARTER`

## Candidate Workspace

Edit only:

- `candidate/workspace/src/ledgerkit/m*.py` (the module files)
- `candidate/refactor-ledger.json`

Migrate every `quote_*` consumer to the v2 ledger contract per `inputs/task.md`.
Do not edit `__init__.py`, `contract.py`, the tests, or anything outside the two
allowed surfaces. The visible tests cover only two anchor consumers and are
intentionally insufficient.

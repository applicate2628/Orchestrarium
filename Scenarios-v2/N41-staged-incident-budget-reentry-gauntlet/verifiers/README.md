# Verifiers

Commands:

- `python verifiers/check_staged_incident_budget.py --bundle-shape-only`
- `python verifiers/check_staged_incident_budget.py --expect-start-state`
- `python verifiers/check_staged_incident_budget.py`
- `python verifiers/check_scope.py --changed-path <path>`

The main verifier checks bundle shape, start-state failure IDs, runtime integration behavior,
`candidate/repair-ledger.json`, staged re-entry state, closeout, and patch-budget checks. The scope
verifier compares actual changed paths with the ledger's `requiredChangedPaths`.

# Verifiers

Commands:

- `python verifiers/check_ownership_budget_repair.py --bundle-shape-only`
- `python verifiers/check_ownership_budget_repair.py --expect-start-state`
- `python verifiers/check_ownership_budget_repair.py`
- `python verifiers/check_scope.py --changed-path <path>`

The main verifier checks bundle shape, start-state failure IDs, runtime integration behavior, and
the required `candidate/repair-ledger.json` source, review, validation, and patch-budget checks.
The scope verifier compares actual changed paths with the ledger's `requiredChangedPaths`.

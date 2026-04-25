# N63 Verifiers

- `check_compact_api_migration.py` checks bundle shape, hidden API behavior, migration ledgers,
  review response, closeout, visible test markers, and expected start-state failures.
- `check_scope.py` checks exact changed paths while ignoring generated top-level `.pytest_cache/**`.
- `check_operator_budget.py` checks the visible worker-output budget.

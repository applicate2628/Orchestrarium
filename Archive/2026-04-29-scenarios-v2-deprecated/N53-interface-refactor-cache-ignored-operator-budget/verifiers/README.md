# N53 Verifiers

- `check_interface_refactor.py` checks bundle shape, hidden interface behavior, migration ledger,
  and visible-test markers.
- `check_scope.py` checks changed paths against the scenario allowlist and ledger patch budget.
- `check_operator_budget.py` checks the compact visible-output budget.
- `.pytest_cache/**` is ignored as generated auxiliary cache; non-cache drift is not ignored.

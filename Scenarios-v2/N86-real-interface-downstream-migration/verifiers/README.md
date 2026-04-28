# N86 Verifiers

- `check_real_interface_downstream.py` checks bundle shape, hidden API behavior, hidden downstream
  public-app behavior, migration ledgers, review response, closeout, visible test markers, and
  expected start-state failures.
- `check_scope.py` checks exact changed paths while ignoring generated top-level `.pytest_cache/**`.

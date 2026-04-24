# Verifiers

- `check_stagegate_systems.py` validates bundle shape, start-state failures, and completed behavior.
- `check_scope.py` validates that changed paths stay inside `scenario.yaml` allowed surfaces.
- `check_operator_budget.py` validates that visible worker output stays inside the scoreable budget.
- `check_turnaround_budget.py` validates the prompt-to-worker-output scoreable turnaround budget.

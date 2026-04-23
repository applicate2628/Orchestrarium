# Verifiers

- `check_staged_delivery.py --bundle-shape-only` validates the seeded bundle.
- `check_staged_delivery.py --expect-start-state` validates that the seeded candidate still exposes
  the intended failures.
- `check_staged_delivery.py` validates a completed staged candidate.
- `check_scope.py --changed-path ...` enforces the exact cumulative patch budget.

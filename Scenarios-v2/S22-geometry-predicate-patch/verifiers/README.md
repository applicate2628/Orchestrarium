# Verifiers

`run_geometry_checks.py` supports three modes:

- `--bundle-shape-only` checks the fixture author's bundle contract and metadata alignment
- `--expect-start-state` checks that the bundled candidate root still exhibits the intended
  deterministic failures and no unexpected extra failures
- default mode checks whether a completed candidate run satisfies the full oracle truth table

`check_scope.py` is the scope-diff helper. It validates that declared or supplied changed paths stay
inside the scenario's allowed change surface.

## Expected validation flow for the fixture author

1. run `run_geometry_checks.py --bundle-shape-only`
2. run `run_geometry_checks.py --expect-start-state`
3. optionally run `check_scope.py` with no changed-path arguments to validate the scope manifest

## Expected validation flow after a scored run

1. apply the candidate patch inside `candidate/geometry-owned/`
2. run `python candidate/geometry-owned/tests/test_predicates.py`
3. run `run_geometry_checks.py` to validate the broader oracle truth table
4. use `check_scope.py --changed-path ...` to confirm the diff stayed in bounds

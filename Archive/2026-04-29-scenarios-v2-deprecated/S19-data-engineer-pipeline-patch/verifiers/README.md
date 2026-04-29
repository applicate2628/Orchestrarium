# Verifiers

`check_s19_pipeline_bundle.py` supports three modes:

- `--bundle-shape-only` checks the fixture author's bundle contract and metadata alignment
- `--expect-start-state` checks that the bundled candidate root still exhibits the intended SQL
  failures
- default mode checks whether a completed candidate run satisfies the local validation route

`check_scope.py` is the scope-diff helper. It validates that declared or supplied changed paths stay
inside the scenario's allowed SQL surface.

## Expected validation flow for the fixture author

1. run `check_s19_pipeline_bundle.py --bundle-shape-only`
2. run `check_s19_pipeline_bundle.py --expect-start-state`
3. run `check_scope.py` with no changed-path arguments to validate the scope manifest

## Expected validation flow after a scored run

1. apply the candidate patch inside `candidate/workspace/sql/customer_day_rollup.sql`
2. run `python scripts/validate_customer_day_rollup.py` from `candidate/workspace/`
3. run `check_s19_pipeline_bundle.py` to validate the completed run
4. use `check_scope.py --changed-path candidate/workspace/sql/customer_day_rollup.sql` to confirm
   the diff stayed in bounds

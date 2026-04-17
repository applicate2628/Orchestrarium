# Verifiers

`run_graphics_checks.py` supports three modes:

- `--bundle-shape-only` checks the fixture author's bundle contract and metadata alignment
- `--expect-start-state` checks that the bundled candidate root still exhibits the intended
  rendering-pipeline failures and nothing else
- default mode checks whether a completed candidate run satisfies the deterministic frame oracle and
  the direct local test file

`check_scope.py` is the scope-diff helper. It validates that declared or supplied changed paths stay
inside the scenario's allowed change surface.

## Expected validation flow for the fixture author

1. run `python verifiers/run_graphics_checks.py --bundle-shape-only`
2. run `python verifiers/run_graphics_checks.py --expect-start-state`
3. optionally run `python verifiers/check_scope.py` with no changed-path arguments to validate the
   scope manifest

## Expected validation flow after a scored run

1. apply the candidate patch inside `candidate/graphics-owned/`
2. run `python tests/test_renderer.py` from `candidate/graphics-owned/`
3. run `python verifiers/run_graphics_checks.py` from the bundle root
4. use `python verifiers/check_scope.py --changed-path ...` to confirm the diff stayed in bounds

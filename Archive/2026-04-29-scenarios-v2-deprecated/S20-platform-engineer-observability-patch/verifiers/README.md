# Verifiers

`check_s20_platform_bundle.py` supports three modes:

- `--bundle-shape-only` checks the fixture author's bundle contract and metadata alignment
- `--expect-start-state` checks that the bundled candidate root still exhibits the intended
  observability failures
- default mode checks whether a completed candidate run satisfies the local validation route

`check_scope.py` is the scope-diff helper. It validates that declared or supplied changed paths stay
inside the scenario's allowed platform-owned config surface.

## Expected validation flow for the fixture author

1. run `python verifiers/check_s20_platform_bundle.py --bundle-shape-only`
2. run `python verifiers/check_s20_platform_bundle.py --expect-start-state`
3. run `python verifiers/check_scope.py` with no changed-path arguments to validate the scope
   manifest

## Expected validation flow after a scored run

1. apply the patch inside `candidate/platform-owned/`
2. run `python scripts/validate_observability_patch.py` from `candidate/platform-owned/`
3. run `python verifiers/check_s20_platform_bundle.py` from the bundle root
4. use `python verifiers/check_scope.py --changed-path ...` to confirm the diff stayed in bounds

# Verifier

`check_dependency_order.py` - deterministic, read-only, executes no candidate code.

## Modes

- `--bundle-shape-only` - validate the bundle contract and scenario.yaml metadata.
- (default) - validate the completed packet against the hidden-derivation oracle.
- `--expect-start-state` - assert the shipped blank candidate fails with exactly the expected ids.

## Four-probe validation

1. Reference PASS: copy `oracle/reference/*` over `candidate/` -> PASS.
2. Vacuous FAIL: a memo with all headers/phrases but a witness without a derived edge / wrong order -> FAIL.
3. Decoy FAIL: an explicit-only order (c-cache before d-auth, empty derived_dependencies) that ignores
   the prose constraint -> FAIL on `witness-phase-order` and `witness-missing-derived-edge`.
4. Near-peer separation: the prose-derived edge flips two positions, so two strong models that both sort
   correctly land on different orders depending on whether they read and derived constraint C1.

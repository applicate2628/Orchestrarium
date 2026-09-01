# Verifier

`check_quantile_dispersion.py` - deterministic, read-only, executes no candidate code.

## Modes

- `--bundle-shape-only` - validate the bundle contract and scenario.yaml metadata only.
- (default) - validate the completed candidate packet against the hidden numeric oracle.
- `--expect-start-state` - assert the shipped blank candidate fails with exactly the expected
  start-state failure ids (used to prove the scaffold is a real start state, not a passing stub).

## Four-probe validation

1. Reference PASS: copy `oracle/reference/{quantile-dispersion-memo.md,witness-ledger.json}` over
   `candidate/` and run default mode -> PASS.
2. Vacuous FAIL: a keyword-stuffed memo with all headers/phrases but no witness numbers -> FAIL.
3. Decoy FAIL: an adversarial answer that follows plausible-but-wrong conventions (linear-interpolation
   percentiles, sample variance, naive fixed-precision dispersion) -> FAIL on the flipped cases.
4. Near-peer separation: three cases flip the gate verdict between the correct upper-rank/population
   conventions and the interpolation/sample conventions, so two strong models that differ only in
   convention adherence land on opposite verdicts.

The verifier runs from the private scorer root and never executes candidate-authored code, so it needs
no `BENCH_EXEC_ROOT` exec split.

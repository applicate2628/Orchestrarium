# Verifiers

`check_s21_toolchain_bundle.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract, including the exact
  `scenario.yaml` field set and required bundle files
- default mode checks whether a scored run completed the toolchain repair correctly

## What the full verifier expects after a run

- only the three editable files are allowed to differ from the protected candidate baseline
- `package.json` exposes `validate:scenario-bundle` as `node toolchain/package-bundle.mjs`
- `bundle-plan.json` uses `dist` and publishes only `dist/**` plus `README.md`
- the package manifest points `main`, `bin`, `exports`, and `files` at `dist`
- the editable files contain no `T29` or legacy runner references
- the local validation command reports `S21 validation PASS`

# Verifiers

`check_s16_frontend_bundle.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract, including the exact
  `scenario.yaml` field set and required bundle files
- default mode checks whether a scored run completed the frontend UI repair correctly

## What the full verifier expects after a run

- only the three editable browser UI files are allowed to differ from the protected candidate
  baseline
- `node scripts/verify-ui-contract.mjs` reports `S16 UI contract PASS`
- loading, success, empty, and error state requirements all remain encoded in the candidate UI files
- preview infrastructure and browser-check material remain unchanged

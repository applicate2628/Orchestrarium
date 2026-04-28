# Phase 04: Reentry Closeout

Close the staged packet with exact changed paths and verification evidence.

Allowed changes:

- `candidate/workspace/implementation-ledger.json`
- `candidate/workspace/closure.json`
- `candidate/workspace/tests/console-contract.test.mjs`

Requirements:

- `closure.json` must use `contractId: N79-staged-ui-visual-state-reentry-v2`.
- `closure.json` must use `planFingerprint: n79-staged-ui-visual-state-reentry-v2`.
- `changedPaths` must match the required changed path list exactly.
- The closeout must include outcome, residual risk, visible return cue evidence, responsive layout evidence, raster overlay evidence, zero-centered legend evidence, and valid P3 PPM evidence.
- The ledger must include phase `04-reentry-closeout`.
- Cite these commands exactly where applicable: `python verifiers/check_ui_visual_state.py`, `python verifiers/check_scope.py`, and `node tests/console-contract.test.mjs`.

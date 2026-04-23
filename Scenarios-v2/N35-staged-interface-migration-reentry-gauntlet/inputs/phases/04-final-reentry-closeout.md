# Phase 04 - Final Re-Entry Closeout

Fresh worker session. Assume prior chat is gone. Reconstruct the state from candidate files.

Edit `candidate/closure.json` and, if needed, `candidate/migration-state.json`.

The closeout must include:

- plan fingerprint `n35-staged-interface-migration-v1`
- exact changed paths across all phases
- validation command `python candidate/workspace/tests/test_interfaceflow.py`
- review packet outcome summary
- residual risk list, which may be empty but must be present

Do not change source code unless a real remaining defect is visible from local tests.

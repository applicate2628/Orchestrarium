# Candidate

Patch only the owning deploygrid runtime files needed for the retry/report defect, update
`workspace/tests/test_deploygrid.py`, and update `candidate/repair-ledger.json`,
`candidate/reentry-state.json`, and `candidate/closeout.json`. The public API, decoys, docs, legacy
helpers, and UI files are protected by the verifier and scope guard.

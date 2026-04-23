# Phase 02: Runtime Repair

Repair the DeployGrid runtime behavior and strengthen tests.

Allowed edits in this phase:

- `candidate/workspace/src/deploygrid/executor.py`
- `candidate/workspace/src/deploygrid/report.py`
- `candidate/workspace/tests/test_deploygrid.py`
- `candidate/reentry-state.json`

Run the direct tests if possible:

`python -m unittest discover -s tests`

Persist phase progress in `candidate/reentry-state.json`. Do not edit the public API, docs, legacy
helper, UI badge, oracle, or verifier files.

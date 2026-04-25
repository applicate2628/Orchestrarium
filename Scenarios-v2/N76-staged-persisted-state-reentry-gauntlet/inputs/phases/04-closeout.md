# Phase 04: Closeout

Create or update only:

- `candidate/closeout.json`
- optionally `candidate/reentry-state.json`

Close the staged work. The closeout must include:

- `contractId: "N76-W54-staged-persisted-state-reentry"`
- exact `changed paths` matching the scenario allowed implementation surface
- validation commands, including `check_persisted_state_replay_migration.py`
- confirmation of no oracle edits, no verifier edits, no README edits, and no package export edits
- final routing note that this is an `X1/X3 separator candidate`

Do not edit implementation code in this final phase.

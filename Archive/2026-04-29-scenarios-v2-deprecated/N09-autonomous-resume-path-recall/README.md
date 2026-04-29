# N09 Autonomous Resume And Path Recall

`N09` benchmarks the `worker.long-autonomous` reference extra lane on resume continuity. The
candidate must keep using the previously discovered real workspace root during a later follow-up
step instead of drifting to the newest edited decoy path.

## Scenario summary

The task starts with a correct first-pass root discovery. A later follow-up step arrives from a
neutral notes directory and includes recent edits in docs, legacy, and UI decoys. The broken helper
chooses the newest touched root instead of preserving the accepted previous root.

## Expected candidate work

Edit only:

- `candidate/workspace/src/workspace/recallWorkspaceRootAfterEdit.js`

Run both commands from `candidate/workspace/`:

- `node --test`
- `node scripts/verify-path-recall.js`

Do not edit `runPathRecallTask.js`, UI helpers, docs mirrors, legacy copies, tests, scripts, inputs,
oracle, or verifiers.

## What this bundle tests

- path recall after interruption or follow-up work
- respect for previously accepted root context
- no drift to a recently edited mirror
- minimal one-owner-file patch discipline

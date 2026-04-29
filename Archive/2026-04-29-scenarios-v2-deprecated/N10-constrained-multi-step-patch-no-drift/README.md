# N10 Constrained Multi-Step Patch With No Drift

`N10` benchmarks the `worker.long-autonomous` reference extra lane on a constrained multi-step
implementation patch. The candidate must repair three cooperating worker helpers while preserving
the target, the accumulated patch steps, and the verification plan.

## Scenario summary

The broken flow drifts in three ways:

- target selection can choose a docs or legacy decoy instead of the owner scope
- a follow-up patch step replaces earlier steps instead of appending
- the verification plan is overwritten with a weak default

## Expected candidate work

Edit only:

- `candidate/workspace/src/worker/chooseOwnedTarget.js`
- `candidate/workspace/src/worker/appendPatchStep.js`
- `candidate/workspace/src/worker/preserveVerificationPlan.js`

Run both commands from `candidate/workspace/`:

- `node --test`
- `node scripts/verify-patch-flow.js`

Do not edit tests, scripts, docs mirrors, legacy copies, or `runPatchFlow.js`.

## What this bundle tests

- autonomous completion across three linked helper seams
- no unrelated churn after a multi-step patch
- preservation of full verification commands
- correct owner-boundary selection under decoy pressure

# N10 Candidate: Constrained Multi-Step Patch With No Drift

Fix the patch-flow worker helpers without widening scope.

Only these files should change:

- `workspace/src/worker/chooseOwnedTarget.js`
- `workspace/src/worker/appendPatchStep.js`
- `workspace/src/worker/preserveVerificationPlan.js`

Do not edit:

- `workspace/src/runPatchFlow.js`
- `workspace/scripts/**`
- `workspace/test/**`
- `workspace/docs/**`
- `workspace/legacy/**`

Run from `workspace/`:

- `node --test`
- `node scripts/verify-patch-flow.js`

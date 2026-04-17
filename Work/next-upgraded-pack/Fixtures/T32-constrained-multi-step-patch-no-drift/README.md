Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the first concrete new-design fixture for `T32`.

It turns the constrained multi-step patch idea into a runnable worker probe with:

- explicit `broken/` and `control-pass/` copies
- three real owner seams that must cooperate
- contract pressure on target selection, step continuity, and verification preservation
- local `npm test` plus an owner verifier

## Goal

Make the smallest safe fix so the patch flow keeps the real owned target, appends follow-up
steps instead of replacing them, and preserves the full verification plan without drifting into
docs mirrors or helper decoys.

## Real owner seams

Only these files should need code fixes:

- `workspace/src/worker/chooseOwnedTarget.js`
- `workspace/src/worker/appendPatchStep.js`
- `workspace/src/worker/preserveVerificationPlan.js`

## Wrong but tempting surfaces

- `workspace/src/runPatchFlow.js`
- `workspace/scripts/chooseOwnedTarget.js`
- `workspace/scripts/preserveVerificationPlan.js`
- `workspace/test/patchFlow.test.js`
- `workspace/docs/chooseOwnedTarget.js`
- `workspace/legacy/preserveVerificationPlan.js`

## Verification

Run both commands from inside either copy's `workspace/` root:

- `npm test`
- `node scripts/verify-patch-flow.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the fix lands only in the three real worker helpers
4. the full verification plan survives the handoff
5. decoy and mirror files stay unchanged

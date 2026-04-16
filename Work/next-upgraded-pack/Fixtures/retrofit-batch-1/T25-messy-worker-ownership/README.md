Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T25 / legacy G15`.

It preserves the old messy worker-ownership semantics, but upgrades the lane with:

- explicit `broken/` and `control-pass/` copies
- stronger anti-brittle pressure against exact-root and exact-target predicates
- explicit anti-drift checks for test-surface and decoy-helper files
- generic alternate-root verification so one hardcoded app name cannot sneak through

## Goal

Make the smallest safe fix so the worker finds the real app root, chooses the real owning
source file, and preserves prior repair session state across the later follow-up step without
falling back to brittle exact-path logic.

## Real owner seams

Only these files should need code fixes:

- `repo/apps/demo-app/src/workspace/findProjectRoot.js`
- `repo/apps/demo-app/src/path/findOwnedTarget.js`
- `repo/apps/demo-app/src/session/mergeRepairSession.js`

Tempting but wrong surfaces:

- `repo/apps/demo-app/src/runOpenWorkerTask.js`
- `repo/apps/demo-app/src/runFollowupWorkerTask.js`
- `repo/apps/demo-app/test/runWorkerOwnershipTask.test.js`
- `repo/docs/notes/findProjectRoot.js`
- `repo/legacy/findOwnedTarget.js`
- `repo/apps/demo-app-shadow/src/session/mergeRepairSession.js`

## Verification

Run all commands from inside either copy's `repo/apps/demo-app/` root:

- `npm test`
- `node scripts/verify-open-worker.js`
- `node scripts/verify-followup-worker.js`

The fixture is valid only when:

1. the `broken/` copy fails required checks
2. the `control-pass/` copy passes all required checks
3. the fix lands only in the three real owner helpers
4. alternate real root names still work without hardcoded `demo-app` logic
5. test and decoy helper files stay unchanged

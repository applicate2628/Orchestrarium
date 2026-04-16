Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T28 / legacy G18`.

It preserves the old reviewer-to-worker transition semantics, but upgrades the lane with:

- explicit `broken/` and `control-pass/` copies
- stronger `docs`, `legacy`, and `shadow` echoes of the same issue
- generic transition checks across more than one review finding family
- anti-drift verification for review artifacts and decoy helper files

## Goal

Make the smallest safe fix so the worker patch plan carries the real review finding into the
owning source file, preserves the same finding id through the handoff, and keeps the same
verification obligations instead of drifting to a docs echo or inventing a new patch story.

## Real owner seam

Only this file should need a code fix:

- `workspace/src/worker/convertReviewToPatchPlan.js`

## Wrong but tempting surfaces

- `workspace/src/review/deriveFindings.js`
- `workspace/src/runReviewerWorkerFlow.js`
- `workspace/test/runReviewerWorkerFlow.test.js`
- `workspace/scripts/deriveFindings.js`
- `workspace/scripts/convertReviewToPatchPlan.js`
- `workspace/docs/lanePriorityResolver.js`
- `workspace/docs/feature-space/lanePriorityResolver.js`
- `workspace/legacy/lanePriorityResolver.js`
- `workspace/legacy/feature-space/lanePriorityResolver.js`
- `workspace-shadow/src/routing/lanePriorityResolver.js`
- `workspace-shadow/src/feature-space/routing/lanePriorityResolver.js`

## Verification

Run both commands from inside either copy's `workspace/` root:

- `npm test`
- `node scripts/verify-reviewer-worker.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the fix lands only in the worker-side review-conversion helper
4. generic behavior survives more than one review finding family
5. decoy files stay unchanged

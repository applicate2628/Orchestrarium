Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the normalized runnable fixture for `T16 / legacy G06`.

It upgrades the backend / platform implementation lane into the shared owner-selection contract
with:

- explicit `broken/` and `control-pass/` copies
- one real owner seam
- anti-drift checks for decoys and backend-adjacent helper files
- generic owner selection across more than one backend basename

## Goal

Make the smallest safe fix so the worker chooses the real owning source file instead of similarly
named `docs`, `scripts`, or `legacy` decoys.

## Real owner seam

Only this file should need a code fix:

- `workspace/src/path/findOwnedTarget.js`

Tempting but wrong surfaces:

- `workspace/src/runBoundedWorkerTask.js`
- `workspace/test/runBoundedWorkerTask.test.js`
- `workspace/docs/notes/lanePriorityResolver.js`
- `workspace/docs/notes/buildGraphSummary.js`
- `workspace/scripts/findOwnedTarget.js`
- `workspace/scripts/buildGraphSummary.js`
- `workspace/legacy/findOwnedTarget.js`
- `workspace/legacy/buildGraphSummary.js`

## Verification

Run from inside either copy's `workspace/` root:

- `node --test`
- `node scripts/verify-owner.js`

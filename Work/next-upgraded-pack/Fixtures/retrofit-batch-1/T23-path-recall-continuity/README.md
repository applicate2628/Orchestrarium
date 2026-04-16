Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T23 / legacy G13`.

It preserves the old path-recall-after-prior-edits semantics, but upgrades the lane with:

- explicit `broken/` and `control-pass/` copies
- distractor edit points that arrive after the real root was already discovered
- stronger generic-path pressure across neutral follow-up locations and alternate root names
- anti-drift verification for same-name decoy files

## Goal

Make the smallest safe fix so the worker keeps using the earlier correct workspace root during
a later follow-up step instead of drifting to a mirror because of the newest distractor edit.

## Real owner seam

Only this file should need a code fix:

- `workspace/src/workspace/recallWorkspaceRootAfterEdit.js`

Tempting but wrong surfaces:

- `workspace/src/runPathRecallTask.js`
- `workspace/src/ui/recallWorkspaceRootAfterEdit.js`
- `docs/project-mirror/src/workspace/recallWorkspaceRootAfterEdit.js`
- `legacy/project-copy/src/workspace/recallWorkspaceRootAfterEdit.js`

## Verification

Run both commands from inside either copy's `workspace/` root:

- `npm test`
- `node scripts/verify-path-recall.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the fix lands only in the real recall helper
4. continuity survives neutral follow-up locations, separator changes, and alternate real root names
5. decoy files stay unchanged

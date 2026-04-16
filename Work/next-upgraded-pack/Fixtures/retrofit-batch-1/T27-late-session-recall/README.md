Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T27 / legacy G17`.

It preserves the old late-session recall semantics, but upgrades the lane with:

- explicit `broken/` and `control-pass/` copies
- stronger `docs`, `legacy`, and `shadow` follow-up drifts
- generic recall checks across more than one source scope
- anti-drift verification for non-owner helpers and decoy files

## Goal

Make the smallest safe fix so the worker preserves the broader owned source scope across
the later follow-up step instead of shrinking to the last edited leaf directory and
drifting to decoy follow-up targets.

## Real owner seams

Only these files should need code fixes:

- `workspace/src/session/carryForwardOwnerScope.js`
- `workspace/src/session/resolveFollowupTarget.js`

## Wrong but tempting surfaces

- `workspace/src/runRecallWorkflow.js`
- `workspace/test/runRecallWorkflow.test.js`
- `workspace/scripts/carryForwardOwnerScope.js`
- `workspace/scripts/resolveFollowupTarget.js`
- `workspace/docs/findOwnedTarget.js`
- `workspace/docs/feature-space/findOwnedTarget.js`
- `workspace/legacy/findOwnedTarget.js`
- `workspace/legacy/feature-space/findOwnedTarget.js`
- `workspace-shadow/src/path/findOwnedTarget.js`
- `workspace-shadow/src/feature-space/path/findOwnedTarget.js`

## Verification

Run both commands from inside either copy's `workspace/` root:

- `npm test`
- `node scripts/verify-recall.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the fix lands only in the two real session helpers
4. generic behavior survives more than one source scope
5. decoy helper files stay unchanged

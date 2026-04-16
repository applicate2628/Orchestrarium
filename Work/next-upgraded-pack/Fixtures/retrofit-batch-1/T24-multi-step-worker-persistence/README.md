Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T24 / legacy G14`.

It preserves the old multi-step worker persistence semantics, but upgrades the lane with:

- explicit `broken/` and `control-pass/` copies
- generic multi-step pressure beyond one fixed `locate -> patch -> verify` path
- explicit anti-shortcut checks for carried ownership, verification commands, and handoff notes
- anti-drift verification for same-name decoy helpers

## Goal

Make the smallest safe fix so the worker carries forward the full accumulated session state
across multiple steps instead of replacing it with only the latest step or patch summary.

## Real owner seams

Only these files should need code fixes:

- `workspace/src/session/appendWorkerStep.js`
- `workspace/src/session/carryForwardWorkerState.js`

Tempting but wrong surfaces:

- `workspace/src/runPersistenceWorkflow.js`
- `workspace/src/ui/appendWorkerStep.js`
- `docs/project-mirror/src/session/appendWorkerStep.js`
- `legacy/project-copy/src/session/carryForwardWorkerState.js`

## Verification

Run both commands from inside either copy's `workspace/` root:

- `npm test`
- `node scripts/verify-persistence.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the fix lands only in the two real session helpers
4. generic behavior survives different step counts, root names, and verification-command sets
5. decoy files stay unchanged

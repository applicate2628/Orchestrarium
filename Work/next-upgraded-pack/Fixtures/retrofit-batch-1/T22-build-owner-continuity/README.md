Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T22 / legacy G12`.

It preserves the old worker continuity and nested build-owner discovery semantics, but
upgrades the lane with:

- explicit `broken/` and `control-pass/` copies
- stronger false-root and false-owner decoys
- anti-drift verification for non-owner files

## Goal

Make the smallest safe fix so the real nested workspace can both identify the owning
source file and assemble a coherent build plan across two linked ownership helpers.

## Real build workspace

The actual workspace is:

- `workspace/`

The actual owning helpers are:

- `workspace/src/path/findOwnedTarget.js`
- `workspace/src/workspace/findWorkspaceRoot.js`

## Wrong but tempting surfaces

- `scripts/findOwnedTarget.js`
- `scripts/findWorkspaceRoot.js`
- `docs/notes/lanePriorityResolver.js`
- `docs/notes/buildGraphSummary.js`
- `legacy/lanePriorityResolver.js`
- `legacy/buildGraphSummary.js`
- `workspace/vendor/routing/lanePriorityResolver.js`
- `workspace/vendor/toolchain/buildGraphSummary.js`
- `workspace-shadow/package.json`

## Verification

Run both commands from inside either copy's `workspace/` root:

- `npm test`
- `node scripts/verify-build.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the fix lands in the two real owner helpers
4. generic behavior survives more than one basename and more than one root shape
5. decoy files stay unchanged

Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T26 / legacy G16`.

It preserves the old toolchain-owner ambiguity semantics, but upgrades the lane with:

- explicit `broken/` and `control-pass/` copies
- stronger mirror pressure across `shadow`, `docs`, and `legacy` roots
- generic basename verification across more than one real app
- anti-drift checks for decoy helper files and the runnable task surface

## Goal

Make the smallest safe fix so the real build root is selected instead of shadow, docs,
or legacy mirrors, while keeping the logic generic across more than one app basename.

## Real owner seam

Only this file should need a code fix:

- `repo/apps/service-app/src/toolchain/findBuildRoot.js`

## Wrong but tempting surfaces

- `repo/apps/service-app/src/runToolchainOwnerTask.js`
- `repo/apps/service-app/src/toolchain/collectBuildEntrypoints.js`
- `repo/apps/service-app/test/runToolchainOwnerTask.test.js`
- `repo/docs/notes/findBuildRoot.js`
- `repo/legacy/findBuildRoot.js`
- `repo/apps/service-app-shadow/src/toolchain/collectBuildEntrypoints.js`
- any mirrored `build.config.json` file

## Verification

Run both commands from inside either copy's `repo/apps/service-app/` root:

- `npm test`
- `node scripts/verify-toolchain-owner.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the fix lands only in the real root-selection helper
4. generic behavior survives more than one app basename
5. decoy helper files stay unchanged

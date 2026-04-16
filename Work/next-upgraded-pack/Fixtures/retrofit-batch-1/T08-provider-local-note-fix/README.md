Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T08 / legacy M08`.

It preserves the old bounded micro-fix semantics, but adds:

- explicit broken-state and control-pass copies
- one true owner seam
- wrong-file attraction through decoy roots and decoy same-name files
- anti-drift verification for non-owner files

## Goal

Make the smallest safe fix so `provider_local_note` never leaks into `preferred_slots`.

## Real owner seam

Only this file should need a code fix:

- `workspace/src/providers/mergeLaneVerdict.js`

Tempting but wrong surfaces:

- `workspace/src/ui/mergeLaneVerdict.js`
- `workspace/src/ui/renderLocalNote.js`
- `docs/project-mirror/src/providers/mergeLaneVerdict.js`
- `legacy/project-copy/src/providers/mergeLaneVerdict.js`

## Verification

Run both commands from inside either copy's `workspace/` root:

- `node --test`
- `node scripts/verify-owner.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. decoy files stay unchanged
4. `provider_local_note` remains separate metadata instead of being nulled out or filtered by an over-broad rule

## Next concrete action

Use this fixture as the first retrofit implementation slice inside `retrofit-batch-1/`, then continue with:

1. `T09`
2. `T10`
3. `T22..T25`

Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T09 / legacy M09`.

It preserves the old bounded debugging semantics, but upgrades the lane into a real
worker-side slice with:

- explicit broken-state and control-pass copies
- one true owner seam
- required root-cause note output
- wrong-file attraction through decoy roots and decoy same-name files
- anti-drift verification for non-owner files

## Goal

Make the smallest safe fix so `provider_local_note` stays out of `preferred_slots`,
and record the actual failure mechanism in `workspace/notes/root-cause.md`.

## Real owner seam

Only this file should need a code fix:

- `workspace/src/providers/mergeLaneVerdict.js`

Required diagnosis artifact:

- `workspace/notes/root-cause.md`

Tempting but wrong surfaces:

- `workspace/src/ui/mergeLaneVerdict.js`
- `workspace/src/ui/renderLocalNote.js`
- `workspace/logs/failure.log`
- `workspace/test/failure-context.txt`
- `docs/project-mirror/src/providers/mergeLaneVerdict.js`
- `legacy/project-copy/src/providers/mergeLaneVerdict.js`

## Verification

Run both commands from inside either copy's `workspace/` root:

- `node --test`
- `node scripts/verify-owner.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the fix lands in the actual owner seam
4. the root-cause note names the right file and mechanism
5. decoy files stay unchanged
6. explicit custom provider slots still survive, so brittle filtering does not pass

## Next concrete action

Use this fixture as the root-cause anchor inside `retrofit-batch-1/`, then continue with:

1. `T10`
2. `T22`
3. `T23`

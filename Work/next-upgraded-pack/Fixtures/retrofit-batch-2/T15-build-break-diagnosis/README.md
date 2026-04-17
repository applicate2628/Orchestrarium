Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the normalized runnable fixture for `T15 / legacy G05`.

It upgrades the old build-break diagnosis prompt into a structured toolchain memo probe with:

- explicit `broken/` and `control-pass/` copies
- one bounded diagnosis seam
- exact verification for root cause and reproduction scope

## Goal

Edit only `workspace/out/build-diagnosis.json` so it records the admitted build-break diagnosis
from the supplied packet.

## Real owner seam

Only this file should need to change:

- `workspace/out/build-diagnosis.json`

Tempting but wrong surfaces:

- `workspace/inputs/build-break.md`
- `workspace/inputs/README.md`
- `workspace/scripts/verify-build-diagnosis.js`

## Verification

Run from inside either copy's `workspace/` root:

- `node scripts/verify-build-diagnosis.js`

Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T04 / legacy M04`.

It turns the old phased-planning prompt into a runnable structured planning probe with:

- explicit `broken/` and `control-pass/` copies
- one bounded planning seam
- exact verification for phase order and deferrals

## Goal

Edit only `workspace/out/decision.json` so it records the admitted execution plan from the
supplied planning packet.

## Real owner seam

Only this file should need to change:

- `workspace/out/decision.json`

Tempting but wrong surfaces:

- `workspace/inputs/adr-packet.md`
- `workspace/scripts/verify-decision.js`

## Verification

Run from inside either copy's `workspace/` root:

- `node scripts/verify-decision.js`

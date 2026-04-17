Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T03 / legacy M03`.

It turns the old ADR-style prompt into a runnable structured decision probe with:

- explicit `broken/` and `control-pass/` copies
- one bounded answer seam
- exact provider-vs-path decision verification

## Goal

Edit only `workspace/out/decision.json` so it records the admitted routing decision from the
supplied ADR packet.

## Real owner seam

Only this file should need to change:

- `workspace/out/decision.json`

Tempting but wrong surfaces:

- `workspace/inputs/adr-packet.md`
- `workspace/scripts/verify-decision.js`

## Verification

Run from inside either copy's `workspace/` root:

- `node scripts/verify-decision.js`

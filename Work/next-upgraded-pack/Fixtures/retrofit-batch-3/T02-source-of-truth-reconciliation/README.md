Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T02 / legacy M02`.

It turns the old source-of-truth reconciliation prompt into a runnable structured-output probe with:

- explicit `broken/` and `control-pass/` copies
- one bounded reconciliation seam
- direct grounding in archive-versus-workspace evidence
- exact verification for canonical-source handling

## Goal

Edit only `workspace/out/facts.json` so it captures the admitted source-of-truth reconciliation
from the supplied packet.

## Real owner seam

Only this file should need to change:

- `workspace/out/facts.json`

Tempting but wrong surfaces:

- `workspace/inputs/source-excerpt.md`
- `workspace/scripts/verify-facts.js`

## Verification

Run from inside either copy's `workspace/` root:

- `node scripts/verify-facts.js`

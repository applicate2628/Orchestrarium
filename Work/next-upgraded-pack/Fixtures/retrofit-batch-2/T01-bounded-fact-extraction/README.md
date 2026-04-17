Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T01 / legacy M01`.

It turns the old bounded factual extraction prompt into a runnable structured-output probe with:

- explicit `broken/` and `control-pass/` copies
- one bounded answer seam
- direct grounding in supplied excerpts only
- exact verification for fact coverage

## Goal

Edit only `workspace/out/facts.json` so it captures the admitted benchmark facts from the
supplied excerpt packet.

## Real owner seam

Only this file should need to change:

- `workspace/out/facts.json`

Tempting but wrong surfaces:

- `workspace/inputs/source-excerpt.md`
- `workspace/scripts/verify-facts.js`

## Verification

Run from inside either copy's `workspace/` root:

- `node scripts/verify-facts.js`

The fixture is valid only when:

1. the `broken/` copy fails verification
2. the `control-pass/` copy passes verification
3. the answer stays inside the bounded fact-extraction seam

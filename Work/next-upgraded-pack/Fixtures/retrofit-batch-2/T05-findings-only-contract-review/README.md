Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T05 / legacy M05`.

It keeps the findings-only review contract, but makes the lane runnable with:

- explicit `broken/` and `control-pass/` copies
- one structured findings seam
- exact severity ordering verification
- harmless wording churn already excluded from the expected findings

## Goal

Edit only `workspace/out/findings.json` so it contains only the real findings supported by the
contract packet and synthetic diff.

## Real owner seam

Only this file should need to change:

- `workspace/out/findings.json`

Tempting but wrong surfaces:

- `workspace/inputs/review-packet.md`
- `workspace/scripts/verify-review-findings.js`

## Verification

Run from inside either copy's `workspace/` root:

- `node scripts/verify-review-findings.js`

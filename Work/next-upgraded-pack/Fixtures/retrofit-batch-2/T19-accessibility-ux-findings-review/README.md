Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the normalized runnable fixture for `T19 / legacy G09`.

It keeps the accessibility and UX review lane, but upgrades it into a structured findings probe
with:

- explicit `broken/` and `control-pass/` copies
- one bounded findings seam
- exact verification for severity ordering and next-fix order

## Goal

Edit only `workspace/out/a11y-review.json` so it records the admitted accessibility and UX
findings from the supplied static artifact.

## Real owner seam

Only this file should need to change:

- `workspace/out/a11y-review.json`

Tempting but wrong surfaces:

- `workspace/inputs/review-target.html`
- `workspace/inputs/user-flows.md`
- `workspace/inputs/README.md`
- `workspace/scripts/verify-a11y-review.js`

## Verification

Run from inside either copy's `workspace/` root:

- `node scripts/verify-a11y-review.js`

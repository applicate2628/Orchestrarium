Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the normalized runnable fixture for `T20 / legacy G10`.

It upgrades the static visual review lane into a structured findings probe with:

- explicit `broken/` and `control-pass/` copies
- one bounded visual-review seam
- exact verification for issue ordering and fix priority

## Goal

Edit only `workspace/out/ui-triage.json` so it records the admitted visual review findings from
the supplied static artifact packet.

## Real owner seam

Only this file should need to change:

- `workspace/out/ui-triage.json`

Tempting but wrong surfaces:

- `workspace/inputs/screen.html`
- `workspace/inputs/styles.css`
- `workspace/inputs/interaction-contract.md`
- `workspace/inputs/observed-state.md`
- `workspace/inputs/triage-notes.md`
- `workspace/scripts/verify-ui-triage.js`

## Verification

Run from inside either copy's `workspace/` root:

- `node scripts/verify-ui-triage.js`

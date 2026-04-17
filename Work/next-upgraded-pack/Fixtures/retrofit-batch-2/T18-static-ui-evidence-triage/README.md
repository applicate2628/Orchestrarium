Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the normalized runnable fixture for `T18 / legacy G08`.

It keeps the non-browser static UI evidence lane, but upgrades it into a structured triage probe
with:

- explicit `broken/` and `control-pass/` copies
- one bounded triage seam
- exact verification for issue ranking and fix order

## Goal

Edit only `workspace/out/ui-triage.json` so it captures the admitted static UI triage from the
supplied evidence packet.

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

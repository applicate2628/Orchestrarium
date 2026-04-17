Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the normalized runnable fixture for `T17 / legacy G07`.

It upgrades the static UI structure patch lane into the shared contract with:

- explicit `broken/` and `control-pass/` copies
- one real owner seam
- anti-drift checks for tempting static-style decoys
- non-browser local verification of structure-preserving CSS fixes

## Goal

Make the smallest safe fix so the note panel stays in normal document flow and hidden state removes
it from layout without widening into decoy stylesheets.

## Real owner seam

Only this file should need a code fix:

- `app/styles.css`

Tempting but wrong surfaces:

- `app/screen.html`
- `app/src/readUiState.js`
- `app/components/panel.css`
- `app/components/legacy-panel.css`
- `app/scripts/verify-static-ui.js`

## Verification

Run from inside either `app/` root:

- `npm test`
- `node scripts/verify-static-ui.js`

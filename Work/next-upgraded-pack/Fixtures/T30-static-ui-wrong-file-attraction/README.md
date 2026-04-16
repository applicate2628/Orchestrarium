Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This is the fixture scaffold for `T30`.

## Probe summary

| Field | Value |
|---|---|
| Test ID | `T30` |
| Working name | `static UI wrong-file attraction` |
| Primary lines | `L05 review.ui-static`, `L09 worker.ui-implementation` |
| Reuse model | `G08` static artifact bundle |

## Intended layout pattern

Use the preserved static-UI artifact bundle pattern:

- `README.md`
- `screen.html`
- `styles.css`
- `interaction-contract.md`
- `observed-state.md`
- `triage-notes.md`

## Implementation note

This fixture now uses a hybrid static bundle plus local machine-checkable verifier.

The first real fixture tree lives under:

- `broken/app/`
- `control-pass/app/`

Run the fixture from inside either `app/` root:

- `npm test`
- `node scripts/verify-static-ui.js`

The verifier intentionally checks the real owner seam only:

- `styles.css`

Decoy files exist under:

- `components/panel.css`
- `components/legacy-panel.css`

## Next concrete action

Validate the fixture in this order:

1. one true owner seam
2. several tempting wrong files or decoy edits
3. explicit broken-state and control-pass criteria

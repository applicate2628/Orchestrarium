Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file records the first local validation pass for `T33`.

## Validation result

| Copy | `npm test` | `node scripts/verify-decor.js` |
|---|---|---|
| `broken` | `FAIL` | `FAIL` |
| `control-pass` | `PASS` | `PASS` |

## Fixture read

| Topic | Read |
|---|---|
| real owner seam | `app/src/decor/selectDecorSpec.js` |
| main pressure | decorative accent token and real asset path must stay consistent together |
| decoys | asset mirrors under `legacy/` and `drafts/`, plus local stylesheet distractors |
| modality | non-browser runnable decorative UI fixture |

## Next step

Add `T31..T33` to the batch harness and run the full admitted new-design slice across `X1`, `X2`, and `X3`.

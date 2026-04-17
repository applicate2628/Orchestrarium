Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file records the first local validation pass for `T31`.

## Validation result

| Copy | `npm test` | `node scripts/verify-fallback.js` |
|---|---|---|
| `broken` | `FAIL` | `FAIL` |
| `control-pass` | `PASS` | `PASS` |

## Fixture read

| Topic | Read |
|---|---|
| real owner seam | `workspace/src/fallback/selectAdmittedSignal.js` |
| main pressure | noisy raw notes must not outrank verifier-backed admitted evidence |
| decoys | `docs/`, `legacy/`, `scripts/selectAdmittedSignal.js`, and `reports/noisy-fallback-pass.md` |
| modality | non-browser runnable code fixture |

## Next step

Move to `T32`, then `T33`, before running the admitted `T31..T33` slice across `X1`, `X2`, and `X3`.

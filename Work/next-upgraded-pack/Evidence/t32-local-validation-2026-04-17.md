Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file records the first local validation pass for `T32`.

## Validation result

| Copy | `npm test` | `node scripts/verify-patch-flow.js` |
|---|---|---|
| `broken` | `FAIL` | `FAIL` |
| `control-pass` | `PASS` | `PASS` |

## Fixture read

| Topic | Read |
|---|---|
| real owner seams | `chooseOwnedTarget.js`, `appendPatchStep.js`, `preserveVerificationPlan.js` |
| main pressure | multi-step worker patch must keep the owned target, append repair history, and preserve the full verification contract |
| decoys | `docs/`, `legacy/`, and helper script copies |
| modality | non-browser runnable worker fixture |

## Next step

Move to `T33`, then run the admitted `T31..T33` slice across `X1`, `X2`, and `X3`.

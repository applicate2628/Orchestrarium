Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

Record local broken-state and control-pass validation for:

- `T22-build-owner-continuity`

## Validation summary

| Fixture | Copy | `npm test` | verifier command | Result |
|---|---|---|---|---|
| `T22` | `broken` | `FAIL` | `node scripts/verify-build.js` | `FAIL` |
| `T22` | `control-pass` | `PASS` | `node scripts/verify-build.js` | `PASS` |

## Practical read

| Fixture | What is now validated |
|---|---|
| `T22` | the real nested workspace must be discovered correctly, the true owner files must beat false-root and false-owner decoys, and decoy surfaces must stay unchanged |

## Next action

Continue the worker-heavy retrofit sequence:

1. `T23`
2. `T24`
3. `T25`

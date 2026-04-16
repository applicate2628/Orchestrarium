Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

Record local broken-state and control-pass validation for:

- `T26-toolchain-owner-ambiguity`

## Validation summary

| Fixture | Copy | `npm test` | `node scripts/verify-toolchain-owner.js` | Result |
|---|---|---|---|---|
| `T26` | `broken` | `FAIL` | `FAIL` | `PASS` |
| `T26` | `control-pass` | `PASS` | `PASS` | `PASS` |

## Practical read

| Fixture | What is now validated |
|---|---|
| `T26` | the worker must select the real app build root over `shadow`, `docs`, and `legacy` mirrors while staying generic across more than one app basename and without drifting into decoy helper files |

## Next action

Continue the worker-heavy retrofit sequence:

1. `T27`
2. `T28`

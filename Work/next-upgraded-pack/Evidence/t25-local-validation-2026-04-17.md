Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

Record local broken-state and control-pass validation for:

- `T25-messy-worker-ownership`

## Validation summary

| Fixture | Copy | `npm test` | `node scripts/verify-open-worker.js` | `node scripts/verify-followup-worker.js` | Result |
|---|---|---|---|---|---|
| `T25` | `broken` | `FAIL` | `FAIL` | `FAIL` | `PASS` |
| `T25` | `control-pass` | `PASS` | `PASS` | `PASS` | `PASS` |

## Practical read

| Fixture | What is now validated |
|---|---|
| `T25` | the worker must recover the real app root, pick the real owner helper instead of shadow or notes copies, and preserve prior repair-session state across the follow-up step without brittle exact-path logic or drift into decoy files |

## Next action

Continue the worker-heavy retrofit sequence:

1. `T26`
2. `T27`
3. `T28`

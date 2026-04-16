Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

Record local broken-state and control-pass validation for:

- `T27-late-session-recall`

## Validation summary

| Fixture | Copy | `npm test` | `node scripts/verify-recall.js` | Result |
|---|---|---|---|---|
| `T27` | `broken` | `FAIL` | `FAIL` | `PASS` |
| `T27` | `control-pass` | `PASS` | `PASS` | `PASS` |

## Practical read

| Fixture | What is now validated |
|---|---|
| `T27` | the worker must preserve the broader source scope across a late follow-up step and keep the recalled target inside that earlier scope instead of shrinking to the last edited leaf and drifting to `docs`, `legacy`, or `shadow` decoys |

## Next action

Continue the worker-heavy retrofit sequence:

1. `T28`

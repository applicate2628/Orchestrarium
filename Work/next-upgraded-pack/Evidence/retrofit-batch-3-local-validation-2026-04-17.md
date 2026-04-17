Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This note records local validation for the remaining extended retrofit fixtures:

- `T02`
- `T04`
- `T06`
- `T11`
- `T13`
- `T14`
- `T16`
- `T17`
- `T20`

## Validation summary

| Test | `broken` | `control-pass` |
|---|---|---|
| `T02` | `node scripts/verify-facts.js` -> `FAIL` | `node scripts/verify-facts.js` -> `PASS` |
| `T04` | `node scripts/verify-decision.js` -> `FAIL` | `node scripts/verify-decision.js` -> `PASS` |
| `T06` | `node scripts/verify-perf-memo.js` -> `FAIL` | `node scripts/verify-perf-memo.js` -> `PASS` |
| `T11` | `node scripts/verify-product-brief.js` -> `FAIL` | `node scripts/verify-product-brief.js` -> `PASS` |
| `T13` | `node scripts/verify-perf-memo.js` -> `FAIL` | `node scripts/verify-perf-memo.js` -> `PASS` |
| `T14` | `node scripts/verify-decision.js` -> `FAIL` | `node scripts/verify-decision.js` -> `PASS` |
| `T16` | `node --test` -> `FAIL`; `node scripts/verify-owner.js` -> `FAIL` | `node --test` -> `PASS`; `node scripts/verify-owner.js` -> `PASS` |
| `T17` | `npm test` -> `FAIL`; `node scripts/verify-static-ui.js` -> `FAIL` | `npm test` -> `PASS`; `node scripts/verify-static-ui.js` -> `PASS` |
| `T20` | `node scripts/verify-ui-triage.js` -> `FAIL` | `node scripts/verify-ui-triage.js` -> `PASS` |

## Read

The remaining extended retrofit batch is now runnable under the same hardening contract as the
earlier batches:

- explicit `broken/` and `control-pass/` copies
- one bounded owner seam per fixture
- local machine-checkable verification

## Next action

Run the newly completed extended batch for the active cohort:

- `X1`
- `X2`
- `X3`

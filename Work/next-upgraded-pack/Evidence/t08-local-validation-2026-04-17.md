Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file records the first local validation pass for `T08 / legacy M08` inside the worker-heavy core slice.

## Validation summary

| Fixture | Copy | Command | Outcome |
|---|---|---|---|
| `T08` | `broken` | `node --test` | `FAIL` |
| `T08` | `broken` | `node scripts/verify-owner.js` | `FAIL` |
| `T08` | `control-pass` | `node --test` | `PASS` |
| `T08` | `control-pass` | `node scripts/verify-owner.js` | `PASS` |

## Command roots

| Fixture | Broken root | Control root |
|---|---|---|
| `T08` | `Fixtures/retrofit-batch-1/T08-provider-local-note-fix/broken/workspace/` | `Fixtures/retrofit-batch-1/T08-provider-local-note-fix/control-pass/workspace/` |

## Interpretation

| Signal | Read |
|---|---|
| broken-state evidence | established |
| control-pass evidence | established |
| true-owner verification | present through `workspace/src/providers/mergeLaneVerdict.js` plus dedicated verifier |
| wrong-file attraction | present through same-name UI decoys and mirror roots |
| anti-drift | present through exact-content checks on decoy files |

## Next step

Move to `T09`, then the `T10` workaround decision, before widening further into the worker-heavy core slice.

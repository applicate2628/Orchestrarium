Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file admits local validation for the second retrofit fixture batch that backfills the
remaining steady-state core anchors:

- `T01`
- `T03`
- `T05`
- `T07`
- `T12`
- `T15`
- `T18`
- `T19`
- `T21`

## Validation summary

| Test | Broken copy | Control-pass copy | Read |
|---|---|---|---|
| `T01` | `FAIL` | `PASS` | bounded fact extraction seam behaves correctly |
| `T03` | `FAIL` | `PASS` | ADR decision-structure output seam behaves correctly |
| `T05` | `FAIL` | `PASS` | findings-only review seam behaves correctly |
| `T07` | `FAIL` | `PASS` | performance memo seam behaves correctly |
| `T12` | `FAIL` | `PASS` | product brief grounding seam behaves correctly |
| `T15` | `FAIL` | `PASS` | build-break diagnosis seam behaves correctly |
| `T18` | `FAIL` | `PASS` | static UI evidence triage seam behaves correctly |
| `T19` | `FAIL` | `PASS` | accessibility and UX findings seam behaves correctly |
| `T21` | `FAIL` | `PASS` | worker path-discovery owner seam behaves correctly |

## Verification commands

| Test family | Commands |
|---|---|
| `T01`, `T03`, `T05`, `T07`, `T12`, `T15`, `T18`, `T19` | `node scripts/verify-*.js` inside each copy's `workspace/` root |
| `T21` | `node --test` and `node scripts/verify-owner.js` inside each copy's `workspace/` root |

## Interpretation

| Topic | Read |
|---|---|
| retrofit status | `retrofit-batch-2` is now concrete and locally validated |
| seam discipline | eight fixtures use a single structured-output seam; `T21` remains a real code-fix owner seam |
| execution readiness | the remaining steady-state core anchors are now runnable for `X1`, `X2`, and `X3` |

## Next step

Add `T01`, `T03`, `T05`, `T07`, `T12`, `T15`, `T18`, `T19`, and `T21` to the active cohort
runner, then execute the remaining-core slice for `X1`, `X2`, and `X3`.

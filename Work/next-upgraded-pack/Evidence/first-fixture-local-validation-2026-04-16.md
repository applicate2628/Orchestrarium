Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This file records the first local validation pass for the newly implemented `B4` concrete probes:

- `T29`
- `T30`

## Validation summary

| Fixture | Copy | Command | Outcome |
|---|---|---|---|
| `T29` | `broken` | `npm test` | `FAIL` |
| `T29` | `broken` | `node scripts/verify-owner.js` | `FAIL` |
| `T29` | `control-pass` | `npm test` | `PASS` |
| `T29` | `control-pass` | `node scripts/verify-owner.js` | `PASS` |
| `T30` | `broken` | `npm test` | `FAIL` |
| `T30` | `broken` | `node scripts/verify-static-ui.js` | `FAIL` |
| `T30` | `control-pass` | `npm test` | `PASS` |
| `T30` | `control-pass` | `node scripts/verify-static-ui.js` | `PASS` |

## Command roots

| Fixture | Broken root | Control root |
|---|---|---|
| `T29` | `Fixtures/T29-toolchain-false-root-ambiguity/broken/repo/apps/service-app/` | `Fixtures/T29-toolchain-false-root-ambiguity/control-pass/repo/apps/service-app/` |
| `T30` | `Fixtures/T30-static-ui-wrong-file-attraction/broken/app/` | `Fixtures/T30-static-ui-wrong-file-attraction/control-pass/app/` |

## Interpretation

| Signal | Read |
|---|---|
| broken-state evidence | established for both `T29` and `T30` |
| control-pass evidence | established for both `T29` and `T30` |
| owner verification | present through dedicated verifier scripts |
| anti-hardcode | explicitly present in `T29` alternate-root checks |
| non-browser verifier path | present for `T30` |

## Next step

Keep `B4` open and move to the first retrofit implementation slice in `retrofit-batch-1/`.

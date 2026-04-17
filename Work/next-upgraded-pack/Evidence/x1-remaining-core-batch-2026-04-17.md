Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file admits the `X1` execution pass on the backfilled remaining steady-state core slice:

- `T01`
- `T03`
- `T05`
- `T07`
- `T12`
- `T15`
- `T18`
- `T19`
- `T21`

## Execution surface

| Field | Value |
|---|---|
| row | `X1` |
| active model label | `gpt-5.4` |
| provider path | `codex` |
| execution helper | `Tooling/run-active-cohort-batch.ps1` |
| batch name | `remaining-core-batch` |
| raw local bundle | `.scratch/active-cohort-runs/2026-04-17_05-22-58-X1-remaining-core-batch/` |

## Admitted result

| Test | Wrapper exit | Local verification | Benchmark-surface changes |
|---|---:|---|---|
| `T01` | `0` | `PASS` | `workspace/out/facts.json` |
| `T03` | `0` | `PASS` | `workspace/out/decision.json` |
| `T05` | `0` | `PASS` | `workspace/out/findings.json` |
| `T07` | `0` | `PASS` | `workspace/out/perf-memo.json` |
| `T12` | `0` | `PASS` | `workspace/out/product-brief.json` |
| `T15` | `0` | `PASS` | `workspace/out/build-diagnosis.json` |
| `T18` | `0` | `PASS` | `workspace/out/ui-triage.json` |
| `T19` | `0` | `PASS` | `workspace/out/a11y-review.json` |
| `T21` | `0` | `PASS` | `workspace/src/path/findOwnedTarget.js` |

## Interpretation

| Topic | Read |
|---|---|
| batch verdict | `X1` is admitted green on the full remaining steady-state core slice |
| structured-output discipline | all eight structured probes stayed inside their single output seams |
| worker ownership discipline | `T21` repaired only the intended owner-selection seam |
| result quality | `X1` remains clean with no material caveat on this slice |

## Next step

Run `X2` on the same remaining-core batch, then `X3`, and fold all three rows into the full
steady-state core result surface.

Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file admits the `X2` execution pass on the backfilled remaining steady-state core slice:

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
| row | `X2` |
| active model label | `gpt-5.3-codex-spark` |
| provider path | `codex` |
| execution helper | `Tooling/run-active-cohort-batch.ps1` |
| batch name | `remaining-core-batch` |
| raw local bundle | `.scratch/active-cohort-runs/2026-04-17_05-36-28-X2-remaining-core-batch/` |

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
| batch verdict | `X2` is admitted green on the full remaining steady-state core slice |
| structured-output discipline | all eight structured probes stayed inside their intended output seams |
| worker ownership discipline | `T21` stayed in the expected owner-selection seam |
| result quality | no additional caveat appears on this slice beyond the earlier `T29` widening note from the runnable-pack surface |

## Next step

Run `X3` on the same remaining-core batch, then refresh the combined result surface to the full
steady-state core wording.

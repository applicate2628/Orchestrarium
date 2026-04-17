Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file admits the `X3` execution pass on the current new-design probe slice:

- `T31`
- `T32`
- `T33`

## Execution surface

| Field | Value |
|---|---|
| row | `X3` |
| active model label | `opus 4.7max` |
| provider path | `claude` |
| execution helper | `Tooling/run-active-cohort-batch.ps1` |
| batch name | `new-design-third-batch` |
| raw local bundle | `.scratch/active-cohort-runs/2026-04-17_04-46-29-X3-new-design-third-batch/` |

## Admitted result

| Test | Wrapper exit | Local verification | Benchmark-surface changes |
|---|---:|---|---|
| `T31` | `0` | `PASS` | `workspace/src/fallback/selectAdmittedSignal.js` |
| `T32` | `0` | `PASS` | `workspace/src/worker/appendPatchStep.js`, `workspace/src/worker/chooseOwnedTarget.js`, `workspace/src/worker/preserveVerificationPlan.js` |
| `T33` | `0` | `PASS` | `app/src/decor/selectDecorSpec.js` |

## Interpretation

| Topic | Read |
|---|---|
| batch verdict | `X3` is admitted green on the full current new-design slice |
| noisy-evidence fallback | `T31` stays disciplined with a single fallback-owner helper change |
| constrained multi-step patching | `T32` passes inside the intended worker coordination seam without drift into decoys |
| decorative consistency | `T33` passes with the intended single decor-selector repair |
| ownership discipline | all three slices stayed inside the expected benchmark seams |

## Next step

Write the full current runnable-pack result surface for `X1`, `X2`, and `X3`, then freeze the
current checkpoint.

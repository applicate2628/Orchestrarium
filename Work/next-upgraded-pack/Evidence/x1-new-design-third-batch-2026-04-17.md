Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file admits the `X1` execution pass on the current new-design probe slice:

- `T31`
- `T32`
- `T33`

## Execution surface

| Field | Value |
|---|---|
| row | `X1` |
| active model label | `gpt-5.4` |
| provider path | `codex` |
| execution helper | `Tooling/run-active-cohort-batch.ps1` |
| batch name | `new-design-third-batch` |
| raw local bundle | `.scratch/active-cohort-runs/2026-04-17_04-31-14-X1-new-design-third-batch/` |

## Admitted result

| Test | Wrapper exit | Local verification | Benchmark-surface changes |
|---|---:|---|---|
| `T31` | `0` | `PASS` | `workspace/src/fallback/selectAdmittedSignal.js` |
| `T32` | `0` | `PASS` | `workspace/src/worker/appendPatchStep.js`, `workspace/src/worker/chooseOwnedTarget.js`, `workspace/src/worker/preserveVerificationPlan.js` |
| `T33` | `0` | `PASS` | `app/src/decor/selectDecorSpec.js` |

## Auxiliary side effects

One sandbox run emitted a local `.reports/...` session log inside the disposable copied
workspace. That file is treated as auxiliary sandbox noise rather than a benchmark-surface
mutation.

| Test | Auxiliary local side effect |
|---|---|
| `T33` | `.reports/2026-04/report(codex)-2026-04-17_04-37_t33-decor-fix.md` |

## Interpretation

| Topic | Read |
|---|---|
| batch verdict | `X1` is admitted green on the full current new-design slice |
| noisy-evidence fallback | `T31` stays disciplined with a single fallback-owner helper change |
| constrained multi-step patching | `T32` passes inside the intended worker coordination seam without drift into decoys |
| decorative consistency | `T33` passes with a single decor-selector repair rather than a broad style rewrite |
| ownership discipline | all three slices stayed inside the expected benchmark seams |

## Next step

Run `X2` on the same new-design batch, then `X3`, and fold the three-row read into the
current runnable-pack results surface.

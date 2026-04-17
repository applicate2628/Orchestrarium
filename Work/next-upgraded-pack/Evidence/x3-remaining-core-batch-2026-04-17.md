Date: 2026-04-17
Owner: `$lead`
Status: `BLOCKED`

## Purpose

This file records the attempted `X3` execution pass on the backfilled remaining steady-state core
slice:

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
| row | `X3` |
| active model label | `opus 4.7max` |
| provider path | `claude` |
| execution helper | `Tooling/run-active-cohort-batch.ps1` |
| batch name | `remaining-core-batch` |
| raw local bundle | `.scratch/active-cohort-runs/2026-04-17_05-50-08-X3-remaining-core-batch/` |

## Attempt result

| Test | Wrapper exit | Local verification | Benchmark-surface changes | Read |
|---|---:|---|---|---|
| `T01` | `0` | `FAIL` | `<none>` | provider output was quota banner only |
| `T03` | `0` | `FAIL` | `<none>` | provider output was quota banner only |
| `T05` | `0` | `FAIL` | `<none>` | provider output was quota banner only |
| `T07` | `0` | `FAIL` | `<none>` | provider output was quota banner only |
| `T12` | `0` | `FAIL` | `<none>` | provider output was quota banner only |
| `T15` | `0` | `FAIL` | `<none>` | provider output was quota banner only |
| `T18` | `0` | `FAIL` | `<none>` | provider output was quota banner only |
| `T19` | `0` | `FAIL` | `<none>` | provider output was quota banner only |
| `T21` | `0` | `FAIL` | `<none>` | provider output was quota banner only |

## Blocker evidence

| Topic | Observation |
|---|---|
| raw provider output | all `9 / 9` worker outputs were the same banner: `You've hit your limit · resets 8am (Europe/Moscow)` |
| model activity | no benchmark-surface file changed in any fixture |
| harness read | runner is now stable on zero-change attempts and no longer crashes on empty `changedPaths` |
| benchmark interpretation | this is an upstream provider availability block, not a model-quality fail on the slice |

## Next step

Rerun the same remaining-core batch for `X3` after the provider quota reset window, then refresh
the full steady-state core result surface.

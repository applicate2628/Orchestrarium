Date: 2026-04-20
Owner: `$lead`
Status: `PASS`

## Scope

This file admits the targeted `X1` rerun for `S16`, `S19`, and `S20` after the v2 runner
was patched to make benchmark allowed-surface rules override repository governance session-log
rules inside disposable candidate run roots.

The previous `X1` failures for these three scenarios were scope-drift failures caused by
top-level `.reports/` control-plane artifacts inside the benchmark candidate root. Those failures
are superseded by this rerun. This evidence does not touch or reinterpret `X1/S29`.

## Run

| Item | Value |
|---|---|
| row | `X1` |
| model label | `gpt-5.4` |
| scenarios | `S16`, `S19`, `S20` |
| command | `powershell -NoProfile -ExecutionPolicy Bypass -Command "& '.\Tooling\run-v2-cohort-batch.ps1' -RowId X1 -BatchName 'x1-control-plane-override-rerun-s16-s19-s20-2026-04-20' -ScenarioIds @('S16','S19','S20')"` |
| workdir | `benchmarks/Work/next-upgraded-pack/` |
| run root | `.scratch/v2-cohort-runs/2026-04-20_14-38-39-X1-x1-control-plane-override-rerun-s16-s19-s20-2026-04-20/` |
| runner exit | `0` |

## Scenario Results

| Scenario | Wrapper exit | Verification | Changed paths | Auxiliary paths |
|---|---:|---|---|---|
| `S16` | `0` | `PASS` | `candidate/workspace/src/dashboard.css`, `candidate/workspace/src/dashboard.js`, `candidate/workspace/src/ui-copy.js` | none |
| `S19` | `0` | `PASS` | `candidate/workspace/sql/customer_day_rollup.sql` | none |
| `S20` | `0` | `PASS` | `candidate/platform-owned/deploy/release-api-observability.yaml`, `candidate/platform-owned/observability/collector-config.yaml` | none |

## Control-Plane Check

| Check | Result |
|---|---|
| no `.reports/` under rerun root | `PASS` |
| no `.plans/` under rerun root | `PASS` |
| no `.scratch/` under rerun root | `PASS` |
| no `.codex/`, `.claude/`, or `.gemini/` under rerun root | `PASS` |
| each `meta/summary.json` has `verificationPassed: true` | `PASS` |
| each `meta/summary.json` has empty `auxiliaryChangedPaths` | `PASS` |

## Superseded Cells

| Scenario | Old admitted X1 cell | New admitted X1 cell | Reason |
|---|---|---|---|
| `S16` | `FAIL` | `PASS` | old failure was benchmark control-plane leakage; rerun stayed inside allowed bundle surface |
| `S19` | `FAIL` | `PASS` | old failure was benchmark control-plane leakage; rerun stayed inside allowed bundle surface |
| `S20` | `FAIL` | `PASS` | old failure was benchmark control-plane leakage; rerun stayed inside allowed bundle surface |

## Effect

| Surface | Before | After |
|---|---:|---:|
| `X1` full v2 `S01..S33 + N01..N07` | `36 / 40` | `39 / 40` |
| `X1` plus `E1 worker.long-autonomous` reference lane | `39 / 43` | `42 / 43` |

## Verdict

`PASS` - `X1/S16`, `X1/S19`, and `X1/S20` are now admitted as scoreable passes.
The remaining admitted full-v2 `X1` failure is `S29`.

Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file admits the first active-cohort execution pass for `X1` on the first worker-heavy
core slice:

- `T08`
- `T09`
- `T10`
- `T22`
- `T23`
- `T24`
- `T25`
- `T29`
- `T30`

## Execution surface

| Field | Value |
|---|---|
| row | `X1` |
| active model label | `gpt-5.4` |
| provider path | `codex` |
| execution helper | `Tooling/run-active-cohort-batch.ps1` |
| batch name | `worker-heavy-first-batch` |
| raw local bundle | `.scratch/active-cohort-runs/2026-04-17_02-07-09-X1-worker-heavy-first-batch/` |

## Admitted result

| Test | Wrapper exit | Local verification | Benchmark-surface changes |
|---|---:|---|---|
| `T08` | `0` | `PASS` | `workspace/src/providers/mergeLaneVerdict.js` |
| `T09` | `0` | `PASS` | `workspace/notes/root-cause.md`, `workspace/src/providers/mergeLaneVerdict.js` |
| `T10` | `0` | `PASS` | `workspace/resume-memo.md` |
| `T22` | `0` | `PASS` | `workspace/src/path/findOwnedTarget.js`, `workspace/src/workspace/findWorkspaceRoot.js` |
| `T23` | `0` | `PASS` | `workspace/src/workspace/recallWorkspaceRootAfterEdit.js` |
| `T24` | `0` | `PASS` | `workspace/src/session/appendWorkerStep.js`, `workspace/src/session/carryForwardWorkerState.js` |
| `T25` | `0` | `PASS` | `repo/apps/demo-app/src/path/findOwnedTarget.js`, `repo/apps/demo-app/src/session/mergeRepairSession.js`, `repo/apps/demo-app/src/workspace/findProjectRoot.js` |
| `T29` | `0` | `PASS` | `repo/apps/service-app/src/toolchain/findWorkspaceRoot.js`, `repo/apps/service-app/src/toolchain/selectOwnerTarget.js` |
| `T30` | `0` | `PASS` | `app/styles.css` |

## Auxiliary side effects

Some sandbox runs emitted local `.reports/...` session logs inside the disposable copied
workspace. Those files are treated as auxiliary sandbox noise rather than benchmark-surface
mutations.

| Test | Auxiliary local side effect |
|---|---|
| `T08` | `.reports/2026-04/report(main)-2026-04-17_02-07_t08-owner-fix.md` |
| `T22` | `.reports/2026-04/report(main)-2026-04-17_02-15_t22-worker-continuity-build.md` |
| `T23` | `.reports/2026-04/report(main)-2026-04-17_02-07_t23-path-recall.md` |
| `T24` | `.reports/2026-04/report(codex)-2026-04-17_02-19_t24-worker-persistence.md` |
| `T25` | `.reports/2026-04/report(codex)-2026-04-17_02-24-42_t25-x1-worker-ownership.md` |
| `T29` | `.reports/2026-04/report(main)-2026-04-17_02-27_t29-owner-fix.md` |
| `T30` | `.reports/2026-04/report(codex)-2026-04-17_02-29_t30-static-ui.md` |

## Interpretation

| Topic | Read |
|---|---|
| batch verdict | `X1` is admitted green on the full first worker-heavy batch |
| toolchain-harder probes | `T29` passes cleanly with the expected owner-seam changes only |
| static-UI-harder probe | `T30` passes cleanly with a single owner-stylesheet change |
| ownership discipline | all nine slices stayed inside the expected benchmark change surfaces |
| harness note | the initial harness batch-summary renderer captured verification output incorrectly and rendered the markdown summary badly, but the raw per-test verification logs remained valid; the pass is admitted from those raw logs and the harness was fixed immediately after discovery |

## Next step

Run `X2` on the same first worker-heavy batch using the repaired harness, then update the
mutable checkpoint before widening the execution surface.

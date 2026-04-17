Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file admits the `X3` execution pass on the first worker-heavy core slice:

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
| row | `X3` |
| active model label | `opus 4.7max` |
| provider path | `claude` |
| execution helper | `Tooling/run-active-cohort-batch.ps1` |
| batch name | `worker-heavy-first-batch` |
| raw local bundle | `.scratch/active-cohort-runs/2026-04-17_03-41-19-X3-worker-heavy-first-batch/` |

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

No benchmark-surface auxiliary mutations were observed in this run. The disposable sandbox stayed
clean outside the expected owner-seam edits.

## Interpretation

| Topic | Read |
|---|---|
| batch verdict | `X3` is admitted green on the full first worker-heavy batch |
| worker depth | `X3` stayed evidence-rich across both diagnostic and continuity-heavy slices, not just the easier owner fixes |
| toolchain-harder probes | `T29` passes cleanly with the expected owner-seam changes only |
| static-UI-harder probe | `T30` passes cleanly with a single owner-stylesheet change |
| ownership discipline | all nine slices stayed inside the intended benchmark change surfaces |
| quota note | the earlier partial `X3` attempt was a provider-quota interruption only; once rerun after the reset window, the row completed cleanly end-to-end |

## Next step

Update the mutable checkpoint to record `X1`, `X2`, and `X3` as admitted on the first worker-heavy
batch, then draft the first execution-backed multi-row interpretation surface before widening the
regular run surface further.

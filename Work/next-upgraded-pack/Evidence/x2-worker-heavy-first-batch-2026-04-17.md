Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file admits the `X2` execution pass on the first worker-heavy core slice:

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
| row | `X2` |
| active model label | `gpt-5.3-codex-spark` |
| provider path | `codex` |
| execution helper | `Tooling/run-active-cohort-batch.ps1` |
| batch name | `worker-heavy-first-batch` |
| raw local bundle | `.scratch/active-cohort-runs/2026-04-17_02-39-03-X2-worker-heavy-first-batch/` |

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
| `T29` | `0` | `PASS` | `repo/apps/service-app/src/runToolchainTask.js`, `repo/apps/service-app/src/toolchain/findWorkspaceRoot.js`, `repo/apps/service-app/src/toolchain/selectOwnerTarget.js` |
| `T30` | `0` | `PASS` | `app/styles.css` |

## Auxiliary side effects

| Test | Auxiliary local side effect |
|---|---|
| `T22` | `.reports/2026-04/report(main)-2026-04-17_02-39-03_T22.md` |
| `T23` | `.reports/2026-04/report(codex)-2026-04-17_02-39-path-recall.md` |
| `T24` | `.reports/2026-04/report(implementation)--fix.md` |
| `T25` | `.reports/2026-04/report(main)-2026-04-17_02-43-t25.txt` |

## Interpretation

| Topic | Read |
|---|---|
| batch verdict | `X2` is admitted green on the first worker-heavy batch at the verifier level |
| broad worker read | `X2` stays valid across the whole admitted slice and remains a credible bounded worker path |
| `T29` caveat | `T29` passed, but the model widened the change surface into `repo/apps/service-app/src/runToolchainTask.js` instead of staying only inside the intended owner seams; this is weaker ownership discipline than `X1` on the same harder toolchain probe |
| `T30` read | `T30` stays clean with a single owner-stylesheet change |
| harness note | the batch completed successfully and the per-test JSON was already intact; only the markdown summary renderer needed a quoting repair immediately after the run |

## Next step

Run `X3` on the same first worker-heavy batch with the repaired harness, then update the
mutable checkpoint with the first multi-row execution-backed comparison.

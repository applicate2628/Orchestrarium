Date: 2026-04-15
Owner: `$lead`
Status: `PASS`

## Purpose

This artifact records the first execution batch on the new worker-trust probes:

- `G12` worker continuity and nested build-owner discovery
- `G13` path recall after prior edits
- `G14` multi-step worker persistence

The first comparison cohort was intentionally limited to:

- `X4` (`opus 4.6max-fb`)
- `X1` (`gpt-5.4`)
- `X3` (native `opus 4.6max`)

## Batch result

| Probe | `X1` | `X3` | `X4` |
|---|---|---|---|
| `G12` | `PASS` | `PASS` | `PASS` |
| `G13` | `PASS` | `PASS` | `PASS` |
| `G14` | `PASS` | `PASS` | `PASS` |

## Verification evidence

| Probe | Verification contract | `X1` | `X3` | `X4` |
|---|---|---|---|---|
| `G12` | `npm test` and `node scripts/verify-build.js` from `workspace/` | `5/5 PASS` and `VERIFY_BUILD_PLAN_OK` | `5/5 PASS` and `VERIFY_BUILD_PLAN_OK` | `5/5 PASS` and `VERIFY_BUILD_PLAN_OK` |
| `G13` | `npm test` and `node scripts/verify-path-recall.js` from `workspace/` | `4/4 PASS` and `VERIFY_PATH_RECALL_OK` | `4/4 PASS` and `VERIFY_PATH_RECALL_OK` | `4/4 PASS` and `VERIFY_PATH_RECALL_OK` |
| `G14` | `npm test` and `node scripts/verify-persistence.js` from `workspace/` | `3/3 PASS` and `VERIFY_PERSISTENCE_OK` | `3/3 PASS` and `VERIFY_PERSISTENCE_OK` | `3/3 PASS` and `VERIFY_PERSISTENCE_OK` |

## Real changed files

| Probe | `X1` | `X3` | `X4` |
|---|---|---|---|
| `G12` | `workspace/src/path/findOwnedTarget.js`, `workspace/src/workspace/findWorkspaceRoot.js` |
|  | plus local `.reports` session log | `workspace/src/path/findOwnedTarget.js`, `workspace/src/workspace/findWorkspaceRoot.js` | `workspace/src/path/findOwnedTarget.js`, `workspace/src/workspace/findWorkspaceRoot.js` |
| `G13` | `workspace/src/workspace/recallWorkspaceRootAfterEdit.js` | `workspace/src/workspace/recallWorkspaceRootAfterEdit.js` | `workspace/src/workspace/recallWorkspaceRootAfterEdit.js` |
| `G14` | `workspace/src/session/appendWorkerStep.js`, `workspace/src/session/carryForwardWorkerState.js` |
|  | plus local `.reports` session log | `workspace/src/session/appendWorkerStep.js`, `workspace/src/session/carryForwardWorkerState.js` | `workspace/src/session/appendWorkerStep.js`, `workspace/src/session/carryForwardWorkerState.js` |

## Accepted findings

| Topic | Accepted finding |
|---|---|
| `X4` bounded worker trust | The first direct trust-comparison batch does **not** show `X4` collapsing on these stronger continuity/path-recall/persistence probes. |
| decoy discipline | The admitted workspaces changed only the owning helpers for each probe. No passing run in this batch edited decoy roots or mirror files. |
| control comparison | `X1`, `X3`, and `X4` all remained green on the same batch, so this first cohort does not currently differentiate them by verdict. |
| boundary | These probes are stronger than `G11`, but they are still bounded fixtures. Passing them is **not** enough to promote `X4` into broad messy-project worker trust or broad toolchain-owner trust. |
| operator concern status | The operator's reported real-project failure mode for `X4` remains plausible, but this batch did not reproduce it yet. The benchmark still needs a messier longer-horizon probe if the goal is to formally capture that degradation. |

## Routing implication

| Question | Current answer |
|---|---|
| Should `X4` stay disallowed as a broad real-project worker owner? | yes |
| Should `X4` be demoted inside bounded worker lanes because of `G12..G14`? | no |
| Did `G12..G14` finally prove the operator's `X4` continuity-collapse claim? | no, not on this first batch |
| What is the next best probe if we want to catch the reported failure? | a messier open-ended repo task with more path fan-out, more ambient context, and longer multi-file continuity than the current bounded fixtures |

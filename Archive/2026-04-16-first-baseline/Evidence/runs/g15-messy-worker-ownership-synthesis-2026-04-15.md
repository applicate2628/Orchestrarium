Date: 2026-04-15
Owner: `$lead`
Status: `PASS`

## Purpose

This artifact records the first real execution batch on `G15`, the messier worker-ownership probe designed to be harder than the earlier bounded worker fixtures.

The same-day cohort now covers:

- `X1` (`gpt-5.4`)
- `X2` (`gpt-5.3-codex-spark`)
- `X3` (native `opus 4.6max`)
- `X4` (`opus 4.6max-fb`)

## Raw verification result

| Probe | `X1` | `X2` | `X3` | `X4` |
|---|---|---|---|---|
| `G15` | all required verifiers green | all required verifiers green | all required verifiers green | all required verifiers green |

## Adjudicated quality verdict

| Row | Adjudicated verdict | Why |
|---|---|---|
| `X2` | `PASS` | clean generic fix; ownership stayed in real app helpers and callers; no test-surface edits and no exact-root hardcode |
| `X3` | `PASS` | clean generic fix; no test-surface edits; ownership stayed in real app helpers and callers |
| `X1` | `PASS` with drift | reached a generic green state, but widened surface by changing the test file to accommodate a helper-signature change |
| `X4` | `REVISE` | produced green verifiers only via a brittle exact-root predicate (`/demo-app/src/`) inside the owning helper, which violates the fixture's anti-hardcoding intent |

## Independent verification evidence

| Row | Verification commands run from `repo/apps/demo-app/` | Result |
|---|---|---|
| `X1` | `npm test`; `node scripts/verify-open-worker.js`; `node scripts/verify-followup-worker.js` | `4/4 PASS`; `VERIFY_OPEN_WORKER_OK`; `VERIFY_FOLLOWUP_WORKER_OK` |
| `X2` | `npm test`; `node scripts/verify-open-worker.js`; `node scripts/verify-followup-worker.js` | `4/4 PASS`; `VERIFY_OPEN_WORKER_OK`; `VERIFY_FOLLOWUP_WORKER_OK` |
| `X3` | `npm test`; `node scripts/verify-open-worker.js`; `node scripts/verify-followup-worker.js` | `4/4 PASS`; `VERIFY_OPEN_WORKER_OK`; `VERIFY_FOLLOWUP_WORKER_OK` |
| `X4` | `npm test`; `node scripts/verify-open-worker.js`; `node scripts/verify-followup-worker.js` | `4/4 PASS`; `VERIFY_OPEN_WORKER_OK`; `VERIFY_FOLLOWUP_WORKER_OK` |

## Changed-file surface

| Row | Changed files |
|---|---|
| `X1` | `repo/apps/demo-app/src/path/findOwnedTarget.js`, `repo/apps/demo-app/src/runOpenWorkerTask.js`, `repo/apps/demo-app/src/runFollowupWorkerTask.js`, `repo/apps/demo-app/src/session/mergeRepairSession.js`, `repo/apps/demo-app/src/workspace/findProjectRoot.js`, `repo/apps/demo-app/test/runOpenWorkerTask.test.js`, local `.reports` session log |
| `X2` | `repo/apps/demo-app/src/path/findOwnedTarget.js`, `repo/apps/demo-app/src/runOpenWorkerTask.js`, `repo/apps/demo-app/src/runFollowupWorkerTask.js`, `repo/apps/demo-app/src/session/mergeRepairSession.js`, `repo/apps/demo-app/src/workspace/findProjectRoot.js`, local `.reports` session log |
| `X3` | `repo/apps/demo-app/src/path/findOwnedTarget.js`, `repo/apps/demo-app/src/runOpenWorkerTask.js`, `repo/apps/demo-app/src/runFollowupWorkerTask.js`, `repo/apps/demo-app/src/session/mergeRepairSession.js`, `repo/apps/demo-app/src/workspace/findProjectRoot.js` |
| `X4` | `repo/apps/demo-app/src/path/findOwnedTarget.js`, `repo/apps/demo-app/src/session/mergeRepairSession.js`, `repo/apps/demo-app/src/workspace/findProjectRoot.js` |

## Accepted findings

| Topic | Accepted finding |
|---|---|
| first messy differentiator | `G15` is the first probe in this line that starts separating rows by **repair quality**, not only by raw green verifiers. |
| `X2` | `gpt-spark` now also clears the messier worker-ownership probe cleanly. Its fix stays generic, root-aware, and inside the real app helper/caller surface. |
| `X3` | Native Claude stayed inside the owning helper/caller surface and solved the task with a generic project-root-aware disambiguation strategy. |
| `X1` | `gpt-5.4` also solved the task generically, but with avoidable drift: it changed the test surface to support its helper-signature change. |
| `X4` | The Claude fallback row no longer looks clean on the messier probe. It achieved green verifiers, but only by embedding an exact `/demo-app/src/` path fragment in the ownership helper, which is too brittle to admit as a clean worker-quality pass. |
| operator-trust signal | This is the first benchmark artifact in the worker-trust line that materially supports the operator's distrust of `X4` on messier real-project-style work, even though it still does not show a raw red failure. |

## Routing implication

| Question | Current answer |
|---|---|
| Did `G15` finally create a meaningful separation between `X3` and `X4` on messy worker work? | yes |
| Does `X2` still look credible on messy bounded worker ownership after `G15`? | yes |
| Does `X4` stay a clean bounded-worker peer to `X3` after `G15`? | no |
| Does `X1` remain broadly strong? | yes, but `G15` shows it can still widen change surface unnecessarily under pressure |
| What should happen next if more confidence is needed? | extend `G15` or a close sibling probe to any later-restored `Q1` path and only revisit Gemini in a fair runtime window |

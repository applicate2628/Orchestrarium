Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This artifact records the full deferred Gemini non-browser catch-up batch across the newer worker-trust and hardening-wave probes:

- `G11`
- `G12`
- `G13`
- `G14`
- `G15`
- `G16`
- `G17`
- `G18`

It supersedes the 2026-04-15 same-day overload defer note for these rows.

## Execution surface

| Target | Model / path | Runtime note |
|---|---|---|
| `X5` | `gemini-3-pro-high-explicit` | fresh 2026-04-16 reruns on isolated no-MCP scratch copies |
| `X6` | `gemini-3.1-flash-lite-preview` | active fallback correction; old compact `gemini3-flash` label is deprecated |

## Verdict grid

| Probe | `X5` | `X6` |
|---|---|---|
| `G11` | `PASS` | `FAIL` |
| `G12` | `PASS` | `PASS` |
| `G13` | `PASS` | `PASS` |
| `G14` | `PASS` | `FAIL` |
| `G15` | `PASS` | `FAIL` |
| `G16` | `PASS` | `PASS` |
| `G17` | `PASS` | `PASS` |
| `G18` | `PASS` | `PASS` |

## Verification basis

| Probe | `X5` host-side verification | `X6` host-side verification |
|---|---|---|
| `G11` | retry scratch copy passed `node --test` | `node --test` failed `3/4` |
| `G12` | `npm test` + `VERIFY_BUILD_PLAN_OK` | `npm test` + `VERIFY_BUILD_PLAN_OK` |
| `G13` | `npm test` + `VERIFY_PATH_RECALL_OK` | `npm test` + `VERIFY_PATH_RECALL_OK` |
| `G14` | `npm test` + `VERIFY_PERSISTENCE_OK` | `npm test` failed; `verify-persistence.js` failed |
| `G15` | `npm test` + `VERIFY_OPEN_WORKER_OK` + `VERIFY_FOLLOWUP_WORKER_OK` from `repo/apps/demo-app/` | `npm test` failed; both follow-up verifiers failed from `repo/apps/demo-app/` |
| `G16` | `npm test` + `VERIFY_TOOLCHAIN_OWNER_OK` | `npm test` + `VERIFY_TOOLCHAIN_OWNER_OK` |
| `G17` | `npm test` + `VERIFY_RECALL_OK` | `npm test` + `VERIFY_RECALL_OK` |
| `G18` | `npm test` + `VERIFY_REVIEWER_WORKER_OK` | `npm test` + `VERIFY_REVIEWER_WORKER_OK` |

## High-signal observations

| Topic | Accepted finding |
|---|---|
| `X5` recovery | `X5` now clears the full non-browser `G11..G18` batch cleanly on 2026-04-16. The 2026-04-15 overload note should no longer be used as a stand-in for current `X5` capability on these lanes. |
| `X6` split profile | `X6` is no longer a blanket defer note either: it now has real green rows on `G12`, `G13`, `G16`, `G17`, and `G18`, but it still fails `G11`, `G14`, and `G15`. |
| `G11` separation | `X5` recovered and passed `G11` after a clean retry, while `X6` still failed owner selection and stayed on docs / legacy decoys. |
| `G14` separation | `X6` preserved step history but still dropped `ownedTarget` / `workspaceRoot`, so the later persistence probe remains a real failure rather than a runtime outage artifact. |
| `G15` separation | `X5` can now complete the messier worker-ownership flow from the real app root, while `X6` still loses the real owner and follow-up state on the same probe. |

## Deviation notes

| Case | Deviation | Accepted read |
|---|---|---|
| `X5/G11` | first fresh 2026-04-16 attempt hung without writing the wrapper output file | the clean retry is the admitted row for this date |
| `X6/G12` | wrapper exit carried abort noise after the model response | host-side verification is green, so the row is admitted as `PASS` |
| several Gemini rows | model output still contains internal tool-availability complaints about `run_shell_command` | host-side verification remains the source of truth; these complaints do not by themselves change the benchmark verdict |

## Raw output pointers

| Target | Output files |
|---|---|
| `X5` | `.scratch/gemini-catchup-2026-04-16/x5-g12.txt`, `.scratch/gemini-catchup-2026-04-16/x5-g13.txt`, `.scratch/gemini-catchup-2026-04-16/x5-g14.txt`, `.scratch/gemini-catchup-2026-04-16/x5-g15.txt`, `.scratch/gemini-catchup-2026-04-16/x5-g16.txt`, `.scratch/gemini-catchup-2026-04-16/x5-g17.txt`, `.scratch/gemini-catchup-2026-04-16/x5-g18.txt`, `.scratch/gemini-catchup-2026-04-16/x5-g11-retry.txt` |
| `X6` | `.scratch/gemini-catchup-2026-04-16/x6-g11.txt`, `.scratch/gemini-catchup-2026-04-16/x6-g12.txt`, `.scratch/gemini-catchup-2026-04-16/x6-g13.txt`, `.scratch/gemini-catchup-2026-04-16/x6-g14.txt`, `.scratch/gemini-catchup-2026-04-16/x6-g15.txt`, `.scratch/gemini-catchup-2026-04-16/x6-g16.txt`, `.scratch/gemini-catchup-2026-04-16/x6-g17.txt`, `.scratch/gemini-catchup-2026-04-16/x6-g18.txt` |

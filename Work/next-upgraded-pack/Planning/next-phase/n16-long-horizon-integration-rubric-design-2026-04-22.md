Date: 2026-04-22
Owner: `$lead`
Status: `APPROVED`

# N16 Long-Horizon Integration + Rubric Design

## Context

`N15` changed the task class to stateful rollback/resume/retry and still tied `X1` and `X3` on
binary correctness. The next attempt should not be another binary-only patch task. It should pair a
larger long-horizon integration patch with a separate score layer.

## Scenario Shape

`N16-release-lane-integration-gauntlet` is a Python implementation scenario on diagnostic surface
`E6`.

The candidate owns a release-lane integration pipeline:

| Component | Responsibility |
|---|---|
| `config.py` | profile resolution, lane defaults, freeze windows |
| `intake.py` | normalize raw release requests without mutating caller input |
| `dedupe.py` | collapse duplicate release intents by semantic key |
| `planner.py` | produce dependency-safe lane plan |
| `scheduler.py` | enforce canary-before-prod and freeze-window rules |
| `ledger.py` | append idempotent release events |
| `notifier.py` | emit exactly-once visible notifications |
| `rollback.py` | roll back only current failed deployment group |
| `audit.py` | preserve source-to-state trace |
| `report.py` | derive release summary from ledger/audit, not transient queues |
| `executor.py` | orchestrate the long-horizon release flow |

Protected public API stays in `api.py`; decoys live under docs/legacy/ui.

## Binary Verifier

The binary verifier stays strict and deterministic:

- exact bundle shape
- expected failing start-state
- completed candidate must pass all integration sequences
- direct tests must pass
- candidate must not read oracle files or hardcode sequence names
- changed paths must stay in the scenario allowlist

## Rubric Layer

The rubric is separate from scenario verifiers. It reads run roots after execution and produces
diagnostic scores without overriding binary PASS/FAIL.

| Metric | Source | Meaning |
|---|---|---|
| correctness | `meta/summary.json` and verifier logs | binary gate result and local verification status |
| patch quality | diff between original scenario and run candidate | scoped files, unnecessary breadth, test coverage, protected-surface hygiene |
| time proxy | file timestamps from prompt/worker-output/summary | elapsed runtime proxy, not provider billing truth |
| cost proxy | `worker-output.txt` byte/word size | reasoning/output bulk proxy, not API cost truth |
| integration quality | static and behavioral signals | whether the patch keeps ownership boundaries clean and avoids oracle literals |

## Expected Signal

If both rows pass binary correctness again, the rubric should still expose a useful top-pair
diagnostic difference: faster completion, smaller output, less churn, better tests, cleaner
ownership, or fewer edge-case misses if one row fails.

The result should be published as:

- `binary`: PASS/FAIL/NOT-RUN
- `rubric`: 0-100
- `time_proxy_seconds`
- `cost_proxy_output_bytes`
- `patch_quality`
- `notes`

This is not a replacement for binary verification. It is the first admitted surface where top-pair
classification may be score-based instead of pretending PASS/PASS contains no signal.

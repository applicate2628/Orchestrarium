Date: 2026-07-12
Owner: `$knowledge-archivist`
Status: `AUTHORED / PRE-REGISTERED`

# V3L05 Stamina Migration (M variant)

This Scenarios-v3 root targets `L05 worker.default-implementation` and is one of a
matched triplet (`-s`, `-m`, `-l`) that measures the **stamina** profile:
sustained, complete, precise application of ONE mechanical transform across many
homogeneous consumers in a single session -- decoupled from per-item depth and from
provider output-budget.

| Field | Value |
|---|---|
| expected_winner | `stamina` (pre-registered -- see `discrimination.yaml`) |
| variant | `m` |
| consumers (`quote_*`) | `18` |
| decoys (`report_*` / `audit_*`) | `9` |
| per-consumer depth | identical across all three variants (add 3 fixed fields) |
| graded measure | `breadth_fraction = migrated_correct / total_consumers` |
| pass threshold | `breadth_fraction >= 0.9` AND zero decoy false-positives |
| triplet measure | completion-vs-length slope (`verifiers/compute_stamina_slope.py`) |

## Why this is not "measuring the wrapper"

Each per-consumer edit adds three short fields, so the whole migrated diff is a few
hundred tokens regardless of variant -- far below any provider's default output-token
cap. The output cap is therefore NOT the binding constraint; what varies is whether a
model sustains complete, precise coverage of all consumers past the point where the
visible tests already pass. Harness resource limits (max output tokens, context
config) are pinned identically for both providers and recorded in telemetry -- see the
`harness_properties` block in `discrimination.yaml`.

## Candidate Contract

| Field | Value |
|---|---|
| role | `$backend-engineer` |
| output files | `candidate/workspace/src/ledgerkit/m*.py`, `candidate/refactor-ledger.json` |
| forbidden shortcut | stop when visible tests pass; blanket-edit that also hits decoys |

## Local Checks

| Check | Command |
|---|---|
| oracle JSON parse | `python -c "import json; json.load(open('Scenarios-v3/V3L05-stamina-migration-m/oracle/stamina-contract.json'))"` |
| bundle shape | `python Scenarios-v3/V3L05-stamina-migration-m/verifiers/check_stamina_migration.py --bundle-shape-only` |
| reference candidate | `python Scenarios-v3/V3L05-stamina-migration-m/verifiers/check_stamina_migration.py --candidate-root <reference>/candidate --metrics-out <path>` |

## Terms and Abbreviations

- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
- `stamina`: profile for sustained single-stream breadth under fixed depth.
- `breadth_fraction`: fraction of hidden consumers correctly migrated.
- `decoy`: a `report_*`/`audit_*` function that must stay unchanged; editing it is a false-positive.

# Expected Findings

The ground-truth memo for `S06` must return `PASS` with exactly four confirmed facts, exactly
four false leads rejected, and exactly two explicit unknowns, presented as the three structured
tables specified in `inputs/task.md`.

## Confirmed Facts ground truth

| id | Question | File | Line (any of) | Symbol (any keyword) | Fact terms (all present) |
|---|---|---|---|---|---|
| F1 | `1`, `1/2`, `1/3` | `candidate/repo-snapshot/benchmarks/runner/collect_scenarios.py` | `7`, `13`, `15`, `19` | `SCENARIO_ROOT`, `glob`, `surface_id`, `load_scenarios_for_surface` | `Scenarios-v2`, `scenario.yaml` |
| F2 | `1`, `1/2`, `2`, `1/3` | `candidate/repo-snapshot/benchmarks/registry/scenario_catalog.py` | `5`–`7`, `14`–`16`, `19`–`22` | `ScenarioRecord`, `from_metadata`, `dataclass`, `bundle_root` | `score_profile` |
| F3 | `2` | `candidate/repo-snapshot/benchmarks/registry/score_profiles.py` | `1`, `2`, `21`, `22` | `PROFILE_WEIGHTS`, `get_profile` | `weights` |
| F4 | `2` | `candidate/repo-snapshot/benchmarks/publication/write_results.py` | `1`, `4`, `5`, `6` | `build_result_row`, `get_profile`, `score_profiles` | `record.score_profile` |

Line tolerance: candidate must cite one of the listed lines per fact. Symbol cell must contain at
least one of the listed keywords. Fact cell must contain all of the listed fact terms.

Exact confirmed-fact count: `4`.

## False Leads Rejected ground truth

| id | Theme keyword (any) | File | Rejection term (all present) |
|---|---|---|---|
| L1 | `legacy config`, `legacy configuration`, `legacy profile`, `legacy module` | `candidate/repo-snapshot/benchmarks/publication/legacy_score_profiles.py` | `write_results`, `score_profiles` |
| L2 | `archived scenario index`, `archived index`, `archive index`, `v1 index` | `candidate/repo-snapshot/benchmarks/archive/scenario_index_v1.yaml` | `export_legacy_index`, `not` |
| L3 | `role-to-surface`, `role-surface mapping`, `role to surface`, `role mapping`, `role_matrix` | `candidate/repo-snapshot/benchmarks/registry/role_matrix.yaml` | `metadata`, `scenario.yaml` |
| L4 | `stale doc`, `legacy doc`, `runtime routing doc`, `routing notes`, `docs page` | `candidate/repo-snapshot/benchmarks/docs/legacy-routing-notes.md` | `migration`, `not` |

Exact false-lead count: `4`.

## Explicit Unknowns ground truth

| id | Unknown keyword (any) | Why term (all present) |
|---|---|---|
| U1 | `entrypoint`, `requested surface id`, `caller`, `scheduler`, `cli` | `not present`, `not included`, `slice`, `bounded` (any one) |
| U2 | `external publication`, `outside the visible`, `legacy profile module`, `other consumer` | `slice`, `bounded`, `not included`, `no evidence` (any one) |

Exact unknown count: `2`.

## Expected gate

`PASS`

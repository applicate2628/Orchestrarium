# Expected Findings

The strongest factual memo should surface the following evidence-backed conclusions from the visible
slice.

## Confirmed current path

1. Scenario discovery starts in `candidate/repo-snapshot/benchmarks/runner/collect_scenarios.py`,
   which sets `SCENARIO_ROOT` to the bundle-local `Scenarios-v2` tree and iterates only
   `*/scenario.yaml` files.
2. Surface filtering is based on each scenario metadata file's `surface_id`, and matching metadata
   is normalized through `ScenarioRecord.from_metadata(...)` in
   `candidate/repo-snapshot/benchmarks/registry/scenario_catalog.py`.
3. `score_profile` is carried from scenario metadata into `ScenarioRecord` and then into result
   output through `candidate/repo-snapshot/benchmarks/publication/write_results.py`.
4. The actual profile weights come from the shared registry table in
   `candidate/repo-snapshot/benchmarks/registry/score_profiles.py`.

## False leads and decoys

1. `candidate/repo-snapshot/benchmarks/docs/legacy-routing-notes.md` describes older migration-time
   behavior and is not sufficient evidence for the live code path.
2. `candidate/repo-snapshot/benchmarks/publication/legacy_score_profiles.py` exists, but the visible
   result-writer imports the registry profile table instead.
3. `candidate/repo-snapshot/benchmarks/archive/scenario_index_v1.yaml` is consumed by
   `candidate/repo-snapshot/benchmarks/tools/export_legacy_index.py`, which looks like export-only
   or archival handling rather than active scenario collection.
4. `candidate/repo-snapshot/benchmarks/registry/role_matrix.yaml` is present in the slice, but the
   visible collector path keys off scenario metadata rather than the role matrix.

## Coverage clues

1. `candidate/repo-snapshot/benchmarks/tests/test_collect_scenarios.py` confirms the collector
   targets `Scenarios-v2` and returns only the matching surface.
2. `candidate/repo-snapshot/benchmarks/tests/test_write_results.py` confirms the result row uses the
   `ScenarioRecord.score_profile` value and yields the expected total weight.

## Explicit unknowns

1. The entrypoint selecting the requested surface ID before `load_scenarios_for_surface(...)` runs
   is not present in this repo slice.
2. No evidence in this slice proves whether any external publication workflow still imports the
   legacy score-profile module outside the visible writer path.

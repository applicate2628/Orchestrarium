# False Leads

These artifacts are intentionally present to create realistic decoy pressure.

- `candidate/repo-snapshot/benchmarks/docs/legacy-routing-notes.md`
  - Looks authoritative, but it explicitly describes older migration behavior and can conflict with
    the current code path.
- `candidate/repo-snapshot/benchmarks/publication/legacy_score_profiles.py`
  - Looks runtime-relevant by name, but the visible writer imports
    `benchmarks.registry.score_profiles.get_profile` instead.
- `candidate/repo-snapshot/benchmarks/archive/scenario_index_v1.yaml`
  - Looks like a scenario registry, but the visible reader for it lives under `tools/`, not the
    runtime collector.
- `candidate/repo-snapshot/benchmarks/registry/role_matrix.yaml`
  - Looks like it might drive bundle selection, but the visible collector filters by scenario
    metadata `surface_id` values.

## Role-drift traps

- turning stale notes into recommendations about what the system should do
- writing a fix plan for the legacy files instead of reporting what they currently do
- treating missing callers or missing imports as confirmed facts instead of bounded unknowns

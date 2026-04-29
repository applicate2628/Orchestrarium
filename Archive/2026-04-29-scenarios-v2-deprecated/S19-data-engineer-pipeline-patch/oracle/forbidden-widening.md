# Forbidden Widening

These changes are out of scope for `S19` even if they appear to make local checks pass:

- editing `candidate/workspace/scripts/validate_customer_day_rollup.py`
- editing `candidate/shared-runners/**`
- editing `candidate/infra-config/**`
- editing `candidate/results-surfaces/**`
- editing `candidate/existing-scenario-roots/**`
- changing any file outside `Scenarios-v2/S19-data-engineer-pipeline-patch/`
- replacing the SQL repair with snapshot edits, scheduler tweaks, or cross-scenario coupling

`S19` is a data-engineer bundle, not a platform, toolchain, or results-publication task.

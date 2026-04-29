# Forbidden Widening

These changes are out of scope for `S20` even if they appear to make local checks pass:

- editing `candidate/platform-owned/scripts/validate_observability_patch.py`
- editing `candidate/platform-owned/fixtures/**`
- editing `candidate/backend-code/**`
- editing `candidate/toolchain-owned/**`
- editing `candidate/shared-runners/**`
- editing `candidate/provider-routing/**`
- editing `candidate/results-surfaces/**`
- changing any file outside `Scenarios-v2/S20-platform-engineer-observability-patch/`
- replacing the config repair with runner glue, provider rerouting, or stale summary edits

`S20` is a platform-engineer bundle, not a backend, toolchain, transport-routing, or results task.

# Phase 02 - Fingerprint Plan

Allowed edits for this phase:

- `candidate/workspace/implementation-ledger.json`
- `candidate/workspace/src/stagegate/fingerprint.py`
- `candidate/workspace/src/stagegate/planner.py`

Repair deterministic planning and fingerprints:

- fingerprints include artifact id, channel, source hash, toolchain revision, sorted features, and
  sorted env tokens
- fingerprints must not include machine paths or workspace paths
- dependency order stages prerequisites before dependents even when dependents have higher priority
- conflicting modes `signed` plus `unsigned-dev`, and `asan` plus `release-fast`, are rejected

Update `implementation-ledger.json` with phase id `02-fingerprint-plan`, owner
`toolchain-engineer`, and source ids `S5` through `S8`.

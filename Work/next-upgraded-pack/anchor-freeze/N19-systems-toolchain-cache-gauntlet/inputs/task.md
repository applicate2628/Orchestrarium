# Task

You are acting as `$toolchain-engineer` on a bounded systems/toolchain implementation bundle.

## Goal

Repair the build-gate planning package in `candidate/workspace/` so it can safely select build
roots, derive portable cache keys, order dependent build requests, handle cache hits, and always
release toolchain locks after success or failure.

## Required output

Update only the editable files listed in `scenario.yaml`.

## Required behavior

- active profile configuration wins over stale `legacyProfile` fields
- `BUILDGATE_BUILD_ROOT` may override the profile build root only when it is a valid absolute path
- invalid relative env roots must fall back to the active profile build root
- all returned build roots must be normalized with `/` separators and no trailing slash
- cache keys must be deterministic across machine paths and feature ordering
- cache keys must include target, profile, source hash, toolchain version, and sorted features
- dependency order must release prerequisites before dependents, even when dependents have higher priority
- conflicting features `asan` and `release-fast` must be rejected
- cache hits must skip the build but still report source trace
- locks must be released on success and failure
- source trace from each request must be preserved in ledger/report output

## Disallowed behavior

- do not hardcode workstation paths, drive letters, usernames, or repo roots
- do not edit protected API/model files, docs, legacy helpers, inputs, oracle, or verifiers
- do not add dependencies
- do not weaken the tests to satisfy the verifier

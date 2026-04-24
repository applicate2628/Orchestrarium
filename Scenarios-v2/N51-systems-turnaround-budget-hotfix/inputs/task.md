# Task

You are acting as `$toolchain-engineer` on a bounded systems/toolchain immutable-CI turnaround hotfix bundle.

## Goal

Repair the artifact staging package in `candidate/workspace/` so it can safely select staging
roots, derive portable artifact fingerprints, order dependent staging requests, handle cache
restores, and always release staging leases after success or failure.

## Required output

Update only the editable production implementation files listed in `scenario.yaml`. The visible
tests are the fixed CI baseline and must not be edited; hidden verifier probes own final
correctness.

Keep the visible worker output in `../meta/worker-output.txt` at or below `40000` bytes and complete
within `360` seconds from prompt write to worker-output write. These are scoreable operator
requirements for turnaround systems/toolchain hotfixes. Do not paste full source files, broad
directory listings, repeated test output, or raw transcripts into the final response.

## Required behavior

- active channel configuration wins over stale `legacyChannel` fields
- `STAGEGATE_ROOT` may override the channel staging root only when it is a valid absolute path
- invalid relative env roots must fall back to the active channel staging root
- all returned staging roots must be normalized with `/` separators and no trailing slash
- fingerprints must be deterministic across machine paths, feature ordering, and env-token ordering
- fingerprints must include artifact id, channel, source hash, toolchain revision, sorted features, and sorted env tokens
- dependency order must stage prerequisites before dependents, even when dependents have higher priority
- conflicting modes `signed` plus `unsigned-dev`, and `asan` plus `release-fast`, must be rejected
- cache restores must skip staging but still report source trace and a visible restore reason
- leases must be released on success and failure
- source trace from each request must be preserved in ledger and summary output

## Disallowed behavior

- do not hardcode workstation paths, drive letters, usernames, or repo roots
- do not edit protected API/model files, docs, legacy helpers, inputs, oracle, or verifiers
- do not edit `candidate/workspace/tests/test_stagegate.py`
- do not add dependencies
- do not weaken the tests to satisfy the verifier
- do not exceed the visible operator-output budget
- do not exceed the prompt-to-output turnaround budget

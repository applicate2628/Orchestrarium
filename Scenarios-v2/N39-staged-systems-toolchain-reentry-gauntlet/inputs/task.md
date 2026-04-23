# Task

You are acting as `$toolchain-engineer` on a staged systems/toolchain implementation bundle.

## Goal

Repair the artifact staging package in `candidate/workspace/` so it can safely select staging
roots, derive portable artifact fingerprints, order dependent staging requests, handle cache
restores, always release staging leases after success or failure, and preserve a durable
implementation ledger plus closeout across staged fresh invocations. The recovery layer must
reject stale global-winner sources, keep `$lead` as the recovery owner, and classify route/quota
runtime failures separately from scoreable verifier failures.

## Required output

Update only the editable files listed in `scenario.yaml`.

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
- stale recovery sources must be rejected in favor of the current role-fit scorecard or roadmap
- resume packets must preserve the primary task and visible return cue
- quota, timeout, and route failures must not be labeled as model `FAIL`
- `implementation-ledger.json` must record phase owners, source ids, stale-source rejections, and
  validation commands
- `closure.json` must record exact changed paths, validation commands, outcome, residual risk, and
  the plan fingerprint `n39-staged-toolchain-reentry-v1`

## Disallowed behavior

- do not hardcode workstation paths, drive letters, usernames, or repo roots
- do not edit protected API/model files, docs, legacy helpers, inputs, oracle, or verifiers
- do not add dependencies
- do not weaken the tests to satisfy the verifier
- do not skip the implementation ledger or closure artifacts

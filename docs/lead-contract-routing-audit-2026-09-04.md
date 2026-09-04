# Provider-Neutral Lead and Worker Routing — Deep Review Audit

## Contents

1. [Reviewed state](#1-reviewed-state)
2. [Angles reviewed](#2-angles-reviewed)
3. [Confirmed findings](#3-confirmed-findings)
4. [Corrections applied](#4-corrections-applied)
5. [Rejected overengineering](#5-rejected-overengineering)
6. [Residual Version 1 limits](#6-residual-version-1-limits)
7. [Verification obligations](#7-verification-obligations)
8. [Version 2 handoff](#8-version-2-handoff)
9. [Terms and abbreviations](#9-terms-and-abbreviations)

## 1. Reviewed state

The audit covers the frozen Version 1 baseline, Astra point route, provider-neutral Lead/worker branch, shared subagent operating model, Codex and Claude projections, provider prompt transports, Kimi and Grok admission boundaries, role and mutation contracts, and the new resolver tests.

The provider-neutral route remains stacked on the Astra route. It is a compatibility feature and does not rewrite native role TOML, the role manifest, `role-routing-policy.v1.json`, `agents-mode`, provider adapters, or the parity baseline.

## 2. Angles reviewed

The review used separate passes for:

- semantic preservation across fallback;
- authority and adapter admission;
- provider/runtime/family identity;
- same-host and native-host isolation;
- independent review requirements;
- malformed and adversarial JSON;
- file-system race and link handling on POSIX and Windows-relevant metadata;
- public/private entrypoint ownership;
- determinism and replay identity;
- denial/fallback observability;
- backward compatibility with existing Version 1 tests;
- installer and documentation projection risk;
- scope control and unnecessary abstraction.

## 3. Confirmed findings

### 3.1 A selected route could be mistaken for execution permission

The resolver correctly described itself as nonauthorizing, but the machine result did not explicitly say that provider adapter admission remained required. A caller could incorrectly treat `status = selected` as launch approval.

### 3.2 The decision lacked a digest of the complete request

The output repeated important fields but had no compact identity for the complete candidate set and contract. This weakened ledger correlation and made contract substitution harder to detect.

### 3.3 Provider-native runtime identity was not host-bound

Provider/runtime mapping admitted `codex-native` and `claude-native`, but did not prevent a Codex Lead from selecting `claude-native` or a Claude Lead from selecting `codex-native`. Native execution belongs to the matching host; cross-host execution must use an admitted external CLI adapter.

### 3.4 JSON input had bounded bytes but unbounded shape

Duplicate keys were rejected, but Python's JSON extension values `NaN` and infinity remained accepted, and deeply nested input could trigger parser recursion or excessive post-parse traversal.

### 3.5 File safety covered the leaf but not the full path chain

A non-linked leaf below a linked or replaced ancestor could pass the prior check. Conversely, binding ancestor directory timestamps would be too strict and could fail on unrelated file activity.

### 3.6 The private selection core remained an executable bypass

The public `resolve.py` facade added native-host binding, request fingerprints, strict JSON parsing, path-chain validation, and explicit adapter-admission fields. The preserved `_resolver_base.py` still retained its former command-line entrypoint, so a caller could execute the private file directly and bypass those facade checks.

## 4. Corrections applied

- Added `requestFingerprintAlgorithm` and `requestFingerprint` for every valid request.
- Added `requiresAdapterAdmission` and invariant `executionAuthorized = false`.
- Added typed `E_LEAD_WORKER_V1_NATIVE_RUNTIME_HOST_MISMATCH` rejection.
- Added JSON constant, depth, and node limits with typed CLI failure.
- Added full lexical path-chain link/reparse/junction/type checks before and after the read.
- Added descriptor identity plus leaf size, modification-time, and status-change-time stability.
- Kept ancestor checks identity-based, preventing unrelated sibling changes from invalidating a safe request.
- Kept `resolve.py` as the only supported command-line entrypoint.
- Reduced `_resolver_base.py` to an import-only selection core whose direct execution returns typed denial `E_LEAD_WORKER_V1_PRIVATE_ENTRYPOINT` without reading the supplied request.
- Added a regression test that passes a fully selectable request to the private path and verifies that no candidate is selected.

## 5. Rejected overengineering

A proposed uniqueness rule for `(provider, runtime, model, effort)` was tested and rejected. Version 1 candidates may intentionally represent different availability or admission observations for the same execution identity. Enforcing registry-style uniqueness in a caller-supplied compatibility list broke valid test scenarios without eliminating a concrete launch vulnerability.

The audit also did not add signed snapshots, entitlement probes, automatic rankings, provider admission transitions, scheduler state, or a Lead lease. Those require trusted owners and cross-record validation and belong in Version 2.

The private selection core remains importable by the reviewed facade; Python module privacy is not treated as a hostile-code isolation boundary. Installer/source integrity owns the installed code files, while adapter admission owns actual process launch.

## 6. Residual Version 1 limits

- `policySnapshotId` and `evidenceSnapshotId` are references, not validated signatures.
- The request fingerprint detects mismatch but does not itself prevent replay.
- The pure resolver does not prove that an executable, subscription, credential, or sandbox is currently usable.
- Kimi remains read-only and Grok remains unavailable until their independent adapters say otherwise.
- A privileged local attacker is outside the file-reader threat model.
- The compatibility facade and private selection core should be consolidated only in a deliberate later migration, not during this point release.

## 7. Verification obligations

Before publication:

1. run all three Version 1 resolver suites and the Astra route suite in a full checkout;
2. run Python compilation;
3. run Codex and Claude skill-pack validators;
4. verify installer projection includes `_resolver_base.py`, rejects direct private execution, and keeps `resolve.py` as the public entrypoint;
5. run installer regressions, `git diff --check`, and publication-safety checks;
6. obtain independent review when review quota or another admitted reviewer is available.

The private-entrypoint regression and Python compilation passed in an isolated checkout containing the exact replacement core. The earlier deep-review red/green cycle passed against the hardened facade. Full repository verification remains a separate draft gate.

## 8. Version 2 handoff

Version 2 must replace caller-supplied evidence references with trusted immutable registry, policy, evaluation, and contract snapshots; add exclusive Lead lease fencing; validate cross-record identities; distinguish availability fallback from quality replan and quarantine; and select role portfolios rather than one worker.

GLM and future providers remain absent from Version 1 and enter only through Version 2 admission.

## 9. Terms and abbreviations

- **CLI — Command-Line Interface:** command-line provider execution surface.
- **TOML — Tom's Obvious Minimal Language:** native role configuration format.
- **SHA-256 — Secure Hash Algorithm 256-bit:** request fingerprint algorithm.
- **Admission:** verified permission to use a runtime for a class of work.
- **Compatibility facade:** stable public entrypoint adding checks around a private implementation core.
- **Replay:** reuse of a previously valid decision outside its intended dispatch context.
- **Time-of-check/time-of-use:** race between checking and using a file-system object.

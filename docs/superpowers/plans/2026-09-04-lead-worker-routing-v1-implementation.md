# Provider-Neutral Lead and Worker Routing V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use test-driven development and a fresh independent review gate for each rejected-or-accepted slice.

**Goal:** keep Codex or Claude as the one logical Lead and select one optional Command-Line Interface (CLI) worker with explicit fallback while preserving role, scope, artifact, gate, and execution authority.

**Architecture:** the public `resolve.py` compatibility facade adds strict input, request identity, native-host, and adapter-admission boundaries around the preserved reviewed selection core in `_resolver_base.py`. Existing native roles, policy, manifests, provider adapters, Astra routing, and operator defaults remain unchanged.

**Tech Stack:** Python 3.11+, JavaScript Object Notation (JSON), Markdown, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-04-lead-worker-routing-v1-design.md`

## Global constraints

- Do not modify the frozen Version 1 parity baseline, native role Tom's Obvious Minimal Language (TOML) files, role manifest, `role-routing-policy.v1.json`, or `agents-mode` defaults.
- Do not add General Language Model (GLM) providers to Version 1.
- Do not launch providers from the resolver.
- Do not allow silent fallback, recursive delegation, worker authorization, provider-family spoofing, provider/runtime spoofing, or cross-host native routing.
- Preserve current Kimi and Grok execution admission boundaries.
- Bind decisions to dispatch, policy, role, scope, artifact, gate, candidate evidence, and complete request identity.
- Do not add or use a GitHub Actions workflow.

## Completed implementation slices

### Slice 1 — strict request and candidate contract

- [x] Exact request and candidate shapes.
- [x] Codex/Claude Lead Host restriction.
- [x] Non-authorizing leaf constraints.

### Slice 2 — role, scope, artifact, gate, and evidence binding

- [x] Bind `dispatchId`, `policySnapshotId`, `assignedRole`, `scopeId`, `artifactContract`, and `gateContract`.
- [x] Bind candidate `evidenceSnapshotId`.
- [x] Preserve all contract fields across fallback.

### Slice 3 — capability, mutation, tools, identity, and isolation

- [x] Provider-family and runtime mapping.
- [x] Independent-family exclusion.
- [x] Capability, tool, mutation, provider ceiling, same-host isolation, delegation, and authority checks.

### Slice 4 — availability fallback and strict CLI

- [x] Typed ordinary and hard-failure availability classes.
- [x] Deterministic priority and fallback evidence.
- [x] Duplicate-key, ordinary-file, no-follow leaf, size-limit, file/stdin CLI handling.

### Slice 5 — deep-review hardening

**Tests first:** `tests/test_lead_worker_routing_v1_deep_review.py`

- [x] Add failing tests for request fingerprint, no execution authority, foreign native runtime, non-standard JSON constants, excessive JSON shape, linked ancestors, and non-flaky ancestor snapshots.
- [x] Observe the expected red failures against the pre-hardening resolver.
- [x] Preserve the reviewed Version 1 selection implementation as `_resolver_base.py`.
- [x] Implement the public hardening facade in `resolve.py`.
- [x] Reject cross-host provider-native workers.
- [x] Add Secure Hash Algorithm 256-bit canonical request fingerprint.
- [x] Add `requiresAdapterAdmission = true` and `executionAuthorized = false` for selected decisions.
- [x] Bound JSON depth and node count and reject non-standard constants.
- [x] Validate the complete path chain while ignoring unrelated directory timestamp changes.
- [x] Pass focused deep-review and compatibility tests in the isolated test checkout.

## Remaining integration gate

- [ ] Run `pytest -q tests/test_lead_worker_routing_v1.py tests/test_lead_worker_routing_v1_deep_review.py tests/test_astra_routing_v1.py` in a full checkout.
- [ ] Run `python -m compileall -q src.codex/skills/lead-worker-routing`.
- [ ] Run both provider-pack validators.
- [ ] Verify installer projection includes `_resolver_base.py`.
- [ ] Run installer regressions, documentation checks, `git diff --check`, and publication-safety checks.
- [ ] Obtain independent review on the final head.
- [ ] Update the Pull Request with exact full-checkout evidence before leaving draft state.

## Explicitly deferred to Version 2

- trusted dynamic registry and signed or hash-bound evidence stores;
- Lead lease and stale-epoch fencing;
- adaptive portfolio selection and structured model disagreement;
- GLM and future provider admission;
- quality replan, quarantine, budget, and evidence-expiry policy;
- ledger schema migration and cross-record semantic validator.

## Terms and abbreviations

- **CLI — Command-Line Interface:** provider command-line execution surface.
- **JSON — JavaScript Object Notation:** request serialization format.
- **SHA-256 — Secure Hash Algorithm 256-bit:** fingerprint algorithm.
- **Compatibility facade:** public entrypoint that adds bounded checks while preserving the reviewed selection core.

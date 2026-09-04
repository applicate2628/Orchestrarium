# Provider-Neutral Lead and Worker Routing V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure Version 1 resolver that keeps Codex or Claude as the single logical Lead and selects one admitted optional CLI worker with explicit fallback provenance while preserving the exact role, scope, artifact, and gate contract.

**Architecture:** Add one provider-neutral Codex-canonical skill projected by the existing installer. The resolver consumes a strict request, filters explicit candidates by availability, capability, provider/runtime identity, mutation, tools, independence, isolation, delegation, and authority, then returns one deterministic nonauthorizing route or a typed failure. Existing native roles, role policy, manifests, provider adapters, Astra routing, and operator defaults remain unchanged.

**Tech Stack:** Python 3.11+, JavaScript Object Notation (JSON), Markdown, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-04-lead-worker-routing-v1-design.md`

## Global Constraints

- Do not modify the frozen Version 1 parity baseline, native role TOML, role manifest, `role-routing-policy.v1.json`, or `agents-mode` defaults.
- Do not add General Language Model (GLM) providers to Version 1.
- Do not launch providers from the resolver.
- Do not allow silent fallback, recursive delegation, worker authorization, provider-family spoofing, or provider/runtime spoofing.
- Preserve current Kimi and Grok execution admission boundaries.
- Bind every decision to one dispatch, policy snapshot, role, scope, artifact contract, gate contract, and candidate evidence snapshot.
- Do not add or use a GitHub Actions workflow.

---

### Task 1: Strict request and candidate contract

**Files:**
- Create: `tests/test_lead_worker_routing_v1.py`
- Create: `src.codex/skills/lead-worker-routing/scripts/resolve.py`

**Interfaces:**
- Produces: `resolve_v1_worker_route(request: dict[str, object]) -> dict[str, object]`.
- Produces: compact deterministic CLI JSON through `main(argv: list[str] | None = None) -> int`.

- [x] **Step 1: Write failing tests for Lead Host, exact fields, provider scope, model independence, and nonauthorizing leaf constraints.**
- [x] **Step 2: Run the focused tests and verify failure because the resolver module is absent.**
- [x] **Step 3: Implement strict validation and typed decisions with no candidate selection beyond the minimum needed by the tests.**
- [x] **Step 4: Run the focused tests and verify they pass.**
- [x] **Step 5: Commit the contract and tests.**

### Task 2: Role, scope, artifact, gate, and evidence binding

**Files:**
- Modify: `tests/test_lead_worker_routing_v1.py`
- Modify: `src.codex/skills/lead-worker-routing/scripts/resolve.py`

**Interfaces:**
- Adds request and decision fields: `dispatchId`, `policySnapshotId`, `assignedRole`, `scopeId`, `artifactContract`, `gateContract`, and `excludedProviderFamilies`.
- Adds candidate field: `evidenceSnapshotId`.

- [x] **Step 1: Add failing tests proving that a selected fallback preserves the exact role, scope, policy snapshot, artifact contract, gate contract, and evidence identity.**
- [x] **Step 2: Run the tests and verify failure because the first resolver does not bind those fields.**
- [x] **Step 3: Implement exact validation and deterministic decision projection for the new contract fields.**
- [x] **Step 4: Run the focused tests and verify they pass.**
- [x] **Step 5: Commit the reviewed contract correction.**

### Task 3: Capability, mutation, tool, identity, and isolation filtering

**Files:**
- Modify: `tests/test_lead_worker_routing_v1.py`
- Modify: `src.codex/skills/lead-worker-routing/scripts/resolve.py`

**Interfaces:**
- Produces: `selectedCandidate`, `rejections`, and stable IDs for provider family, runtime, capability, independence, mutation, tool, isolation, delegation, and authority denials.

- [x] **Step 1: Add failing tests for provider/runtime spoofing, excluded provider family, missing capability, insufficient mutation level, missing tools, same-host non-isolation, recursive delegation, and authorizing candidates.**
- [x] **Step 2: Run the focused tests and confirm each new test fails for the missing behavior.**
- [x] **Step 3: Implement deterministic candidate filtering and stable rejection reasons.**
- [x] **Step 4: Run the focused tests and verify all pass.**
- [x] **Step 5: Commit filtering behavior with Task 2.**

### Task 4: Explicit availability fallback and strict CLI input

**Files:**
- Modify: `tests/test_lead_worker_routing_v1.py`
- Modify: `src.codex/skills/lead-worker-routing/scripts/resolve.py`

**Interfaces:**
- Produces: `fallbackApplied`, `fallbackEvents`, `hardFailureObserved`, `requiresOperatorAttention`, and deterministic compact CLI output.

- [x] **Step 1: Add failing tests for subscription absence, quota exhaustion, transport failure, hard auth/contract failures, no selectable candidate, duplicate JSON keys, symbolic-link input, input-size limit, and stdin/file CLI behavior.**
- [x] **Step 2: Run the focused tests and verify expected failures.**
- [x] **Step 3: Implement explicit candidate-order fallback, hard-failure classification, strict JSON parsing, and no-follow ordinary-file input.**
- [x] **Step 4: Run the focused tests and verify pass plus clean stderr.**
- [x] **Step 5: Commit fallback and CLI behavior with Tasks 2 and 3.**

### Task 5: Installable skill and documentation

**Files:**
- Modify: `src.codex/skills/lead-worker-routing/SKILL.md`
- Modify: `src.codex/skills/lead-worker-routing/agents/openai.yaml`
- Modify: `docs/lead-contract-routing-audit-2026-09-04.md`
- Modify: `docs/superpowers/specs/2026-09-04-lead-worker-routing-v1-design.md`
- Modify: `docs/superpowers/plans/2026-09-04-lead-worker-routing-v1-implementation.md`

**Interfaces:**
- Consumes: the resolver command and stable result fields.
- Produces: provider-neutral operator instructions projected by the existing installer.

- [x] **Step 1: Add failing metadata/documentation assertions to the focused test.**
- [x] **Step 2: Run the test and verify failure because the reviewed contract fields are absent from the docs.**
- [x] **Step 3: Update the skill, metadata, audit, spec, and plan without changing existing routing defaults.**
- [x] **Step 4: Run focused tests and Python compilation in the available isolated checkout.**
- [x] **Step 5: Commit documentation and implementation together so the public contract matches the code.**

### Task 6: Integration verification and pull request

**Files:**
- Verify only; update Pull Request body after evidence is available.

**Interfaces:**
- Produces: final branch evidence and a stacked Pull Request targeting `feature/astra-routing-v1`.

- [ ] **Step 1: Run `pytest -q tests/test_lead_worker_routing_v1.py tests/test_astra_routing_v1.py` in a full checkout.**
- [ ] **Step 2: Run `python -m compileall -q src.codex/skills/lead-worker-routing` and `git diff --check` in a full checkout.**
- [ ] **Step 3: Run repository provider-pack validators, installer projection checks, and publication safety checks.**
- [ ] **Step 4: Review the final diff against the spec, especially baseline non-mutation and no hidden provider admission.**
- [ ] **Step 5: Open a draft stacked Pull Request and record exact verification evidence and remaining unavailable checks.**

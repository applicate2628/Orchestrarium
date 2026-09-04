# Provider-Neutral Lead and Worker Routing V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure Version 1 resolver that keeps Codex or Claude as the single logical Lead and selects one admitted optional CLI worker with explicit fallback provenance.

**Architecture:** Add one provider-neutral Codex-canonical skill projected by the existing installer. The resolver consumes a strict request, filters explicit candidates by availability, capability, mutation, tools, isolation, delegation, and authority, then returns one deterministic nonauthorizing route or a typed failure. Existing native roles, role policy, manifests, provider adapters, Astra routing, and operator defaults remain unchanged.

**Tech Stack:** Python 3.11+, JSON, Markdown, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-04-lead-worker-routing-v1-design.md`

## Global Constraints

- Do not modify the frozen Version 1 parity baseline, native role TOML, role manifest, `role-routing-policy.v1.json`, or `agents-mode` defaults.
- Do not add GLM to Version 1.
- Do not launch providers from the resolver.
- Do not allow silent fallback, recursive delegation, or worker authorization.
- Preserve current Kimi and Grok execution admission boundaries.
- Do not add or use a GitHub Actions workflow.

---

### Task 1: Strict request and candidate contract

**Files:**
- Create: `tests/test_lead_worker_routing_v1.py`
- Create: `src.codex/skills/lead-worker-routing/scripts/resolve.py`

**Interfaces:**
- Produces: `resolve_v1_worker_route(request: dict[str, object]) -> dict[str, object]`.
- Produces: compact deterministic CLI JSON through `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write failing tests for Lead Host, exact fields, provider scope, model independence, and nonauthorizing leaf constraints.**
- [ ] **Step 2: Run `pytest -q tests/test_lead_worker_routing_v1.py` and verify failure because the resolver module is absent.**
- [ ] **Step 3: Implement strict validation and typed decisions with no candidate selection beyond the minimum needed by the tests.**
- [ ] **Step 4: Run the focused tests and verify they pass.**
- [ ] **Step 5: Commit the contract and tests.**

### Task 2: Capability, mutation, tool, and isolation filtering

**Files:**
- Modify: `tests/test_lead_worker_routing_v1.py`
- Modify: `src.codex/skills/lead-worker-routing/scripts/resolve.py`

**Interfaces:**
- Consumes: the strict request and candidate structures from Task 1.
- Produces: `selectedCandidate`, `rejections`, and stable IDs for policy denials.

- [ ] **Step 1: Add failing tests for missing capability, insufficient mutation level, missing tools, same-host non-isolation, recursive delegation, and authorizing candidates.**
- [ ] **Step 2: Run the focused tests and confirm each new test fails for the missing behavior.**
- [ ] **Step 3: Implement deterministic candidate filtering and stable rejection reasons.**
- [ ] **Step 4: Run the focused tests and verify all pass.**
- [ ] **Step 5: Commit filtering behavior.**

### Task 3: Explicit availability fallback and CLI

**Files:**
- Modify: `tests/test_lead_worker_routing_v1.py`
- Modify: `src.codex/skills/lead-worker-routing/scripts/resolve.py`

**Interfaces:**
- Produces: `fallbackApplied`, `fallbackEvents`, and deterministic compact CLI output.

- [ ] **Step 1: Add failing tests for `not-entitled`, `quota-exhausted`, transport failure, hard auth/contract failures, no selectable candidate, and stdin/file CLI behavior.**
- [ ] **Step 2: Run the focused tests and verify expected failures.**
- [ ] **Step 3: Implement explicit candidate-order fallback and CLI parsing.**
- [ ] **Step 4: Run the focused tests and verify pass plus clean stderr.**
- [ ] **Step 5: Commit fallback and CLI behavior.**

### Task 4: Installable skill and documentation

**Files:**
- Create: `src.codex/skills/lead-worker-routing/SKILL.md`
- Create: `src.codex/skills/lead-worker-routing/agents/openai.yaml`
- Create: `docs/lead-contract-routing-audit-2026-09-04.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/specs/2026-09-04-lead-worker-routing-v1-design.md`

**Interfaces:**
- Consumes: the resolver command and stable result fields.
- Produces: provider-neutral operator instructions projected by the existing installer.

- [ ] **Step 1: Add failing metadata/documentation assertions to the focused test.**
- [ ] **Step 2: Run the test and verify failure because the skill files are absent.**
- [ ] **Step 3: Write the skill, Codex metadata, audit, and docs index entry without changing existing routing defaults.**
- [ ] **Step 4: Run focused tests, Python compilation, and Markdown link/path checks available in the partial checkout.**
- [ ] **Step 5: Commit documentation and skill projection.**

### Task 5: Integration verification and pull request

**Files:**
- Verify only; update Pull Request body after evidence is available.

**Interfaces:**
- Produces: final branch evidence and a stacked Pull Request targeting `feature/astra-routing-v1`.

- [ ] **Step 1: Run `pytest -q tests/test_lead_worker_routing_v1.py tests/test_astra_routing_v1.py`.**
- [ ] **Step 2: Run `python -m compileall -q src.codex/skills/lead-worker-routing` and `git diff --check` in a full checkout when available.**
- [ ] **Step 3: Run repository validators available through the checked-out branch; record any unavailable full-checkout verification honestly.**
- [ ] **Step 4: Review the final diff against the spec, especially baseline non-mutation and no hidden provider admission.**
- [ ] **Step 5: Open a draft stacked Pull Request and record exact verification evidence.**

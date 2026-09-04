# Lead Worker Pool Version 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure Version 1 resolver and installable skill that preserve one Codex- or Claude-hosted logical Lead while selecting interchangeable eligible CLI workers with explicit cross-provider fallback.

**Architecture:** Keep all existing Version 1 native routing and provider transports unchanged. Add a skill-local resolver that consumes a caller-ranked runtime snapshot, applies hard capability/admission/availability/independence gates, and returns one nonauthorizing route plus complete fallback provenance.

**Tech Stack:** Python 3.11+, JSON, Markdown, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-04-lead-worker-pool-v1-design.md`

## Global Constraints

- Keep `shared/role-routing-policy.v1.json`, native role TOML, role manifests, provider credentials, and operator presets unchanged.
- Version 1 providers are exactly Codex, Claude, Kimi, and Grok.
- GLM is Version 2 only.
- Exact model identifiers are runtime observations, never stable routing policy.
- Every result is nonauthorizing and leaf-only.
- No hidden fallback and no weakening of mutation, tool, capability, or independence gates.
- Do not add or use a GitHub Actions workflow.

---

### Task 1: Pure route contract

**Files:**
- Create: `tests/test_lead_worker_pool_v1.py`
- Create: `src.codex/skills/lead-worker-pool/scripts/resolve.py`

**Interfaces:**
- Consumes: `resolve_v1_worker_route(...)` keyword arguments defined by the spec.
- Produces: one deterministic Version 1 decision dictionary and `--request <json-file>` command-line interface.

- [x] **Step 1: Write failing tests for Lead hosts, ordered candidates, provider fallback, admission, tools, independence, availability states, strict input, and command-line output.**
- [x] **Step 2: Run `pytest -q tests/test_lead_worker_pool_v1.py` and verify failure because `resolve.py` is absent.**
- [x] **Step 3: Implement strict candidate validation, typed rejection trace, deterministic selection, and nonauthorizing output.**
- [x] **Step 4: Run `pytest -q tests/test_lead_worker_pool_v1.py` and verify all resolver tests pass.**
- [x] **Step 5: Run `python -m py_compile src.codex/skills/lead-worker-pool/scripts/resolve.py`.**

### Task 2: Installable skill contract

**Files:**
- Create: `src.codex/skills/lead-worker-pool/SKILL.md`
- Create: `src.codex/skills/lead-worker-pool/agents/openai.yaml`
- Modify: `tests/test_lead_worker_pool_v1.py`

**Interfaces:**
- Consumes: the pure resolver from Task 1 and existing approved provider wrappers.
- Produces: an installed skill discoverable at Lead routing points without editing existing Lead payloads.

- [x] **Step 1: Add a failing metadata test requiring provider-neutral Lead wording, caller-supplied candidate order, GLM exclusion, and no model-version pinning.**
- [x] **Step 2: Run the metadata test and verify it fails because the skill files are absent.**
- [x] **Step 3: Add the skill body and Codex metadata, preserving existing wrapper and external-role authority.**
- [x] **Step 4: Run the complete focused test file and verify all tests pass.**

### Task 3: Review and documentation

**Files:**
- Create: `docs/lead-host-worker-pool-audit-2026-09-04.md`
- Create: `docs/superpowers/specs/2026-09-04-lead-worker-pool-v1-design.md`
- Create: `docs/superpowers/plans/2026-09-04-lead-worker-pool-v1-implementation.md`
- Modify: `docs/README.md`

**Interfaces:**
- Consumes: current `main`, PR 4, PR 5, PR 6, shared operating model, both Lead implementations, external role taxonomy, provider policy, and wrapper admission.
- Produces: a repository-grounded audit, one normative V1 design, one executable implementation plan, and discoverable documentation links.

- [x] **Step 1: Record current ownership boundaries and distinguish already-supported Lead symmetry from missing worker fallback.**
- [x] **Step 2: Record the exact V1/V2 boundary: no GLM or automatic Lead lease in V1.**
- [x] **Step 3: Document explicit fallback states, hard gates, independence, and current provider-admission limitations.**
- [x] **Step 4: Add the audit and specifications to `docs/README.md`.**

### Task 4: Branch verification and publication preparation

**Files:**
- Verify all files changed by Tasks 1–3.

**Interfaces:**
- Consumes: final branch tree.
- Produces: a draft stacked pull request with reproducible evidence and no merge claim.

- [ ] **Step 1: Run the focused Pytest suite and Python compilation in a complete checkout.**
- [ ] **Step 2: Run Codex and Claude provider-pack validators, installer checks, and `git diff --check` in a complete checkout.**
- [ ] **Step 3: Run the repository publication gate without adding GitHub Actions.**
- [ ] **Step 4: Open a draft pull request stacked on the current Astra Version 1 pull request and record any verification unavailable in the connector-only environment.**

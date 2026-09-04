# Adaptive Model Portfolio Routing V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a pure, dynamic, provider-neutral Version 2 resolver that selects a quality-first multi-model portfolio under a Codex or Claude Lead.

**Architecture:** Strict registry, request, slot, candidate, and policy contracts feed a bounded complete-search resolver. Hard gates remove inadmissible candidates and portfolios; deterministic lexicographic ranking then favors required quality, scope coverage, family and approach diversity, challenge and evidence, followed by accepted-result cost and latency. Exact model generations exist only in registry snapshots.

**Tech Stack:** Python 3.11+, JSON Schema Draft 2020-12, JSON, SHA-256, Markdown, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-04-adaptive-model-portfolio-routing-v2-design.md`

## Global Constraints

- Keep Codex or Claude as the one logical Lead Host.
- Do not hardcode exact model generation identifiers or a permanent vendor order.
- Do not launch providers, manage credentials, or mutate Version 1 runtime state.
- Run hard admission and quality gates before ranking.
- Rank quality, scope, diversity, challenge, and evidence before cost and latency.
- Workers remain leaf-only and nonauthorizing.
- Refuse incomplete or oversized search spaces instead of silently approximating.
- Do not add or use a GitHub Actions workflow.

---

### Task 1: Version 2 schemas and strict parser

**Files:**
- Create: `shared/schemas/model-registry.v2.schema.json`
- Create: `shared/schemas/model-routing-request.v2.schema.json`
- Create: `tests/test_model_routing_v2.py`
- Create: `scripts/model_routing/resolve_v2.py`

**Interfaces:**
- Produces: `resolve_v2_portfolio(request: dict[str, object]) -> dict[str, object]`.
- Produces: strict registry, Lead, policy, task, slot, and candidate validation helpers.

- [ ] **Step 1: Write failing tests for arbitrary future model IDs, Lead Host validation, exact fields, provider-family consistency, malformed JSON types, and schema presence.**
- [ ] **Step 2: Run `pytest -q tests/test_model_routing_v2.py` and verify failure because schemas and resolver are absent.**
- [ ] **Step 3: Add schemas and minimal strict validation returning typed nonauthorizing decisions.**
- [ ] **Step 4: Run focused tests and verify pass.**
- [ ] **Step 5: Commit schemas and parser.**

### Task 2: Candidate and slot hard gates

**Files:**
- Modify: `tests/test_model_routing_v2.py`
- Modify: `scripts/model_routing/resolve_v2.py`

**Interfaces:**
- Produces: per-slot eligible candidates and typed `candidateExclusions`.

- [ ] **Step 1: Add failing tests for availability, admission, mutation, capabilities, tools, quality, reliability, sample support, same-host isolation, delegation, and authority.**
- [ ] **Step 2: Verify the new tests fail for missing gate behavior.**
- [ ] **Step 3: Implement minimal deterministic candidate filtering.**
- [ ] **Step 4: Run focused tests and verify pass.**
- [ ] **Step 5: Commit hard gates.**

### Task 3: Complete portfolio search and cross-slot constraints

**Files:**
- Modify: `tests/test_model_routing_v2.py`
- Modify: `scripts/model_routing/resolve_v2.py`

**Interfaces:**
- Produces: complete combinations including `None` for optional slots, cross-slot independence enforcement, and bounded search refusal.

- [ ] **Step 1: Add failing tests for required/optional slots, earlier-phase visibility, independent reviewer constraints, required scope, minimum family diversity, and search-space cap.**
- [ ] **Step 2: Verify failures identify missing portfolio behavior.**
- [ ] **Step 3: Implement bounded exhaustive search and hard portfolio gates.**
- [ ] **Step 4: Run focused tests and verify pass.**
- [ ] **Step 5: Commit portfolio construction.**

### Task 4: Quality-first adaptive ranking

**Files:**
- Modify: `tests/test_model_routing_v2.py`
- Modify: `scripts/model_routing/resolve_v2.py`

**Interfaces:**
- Produces: deterministic lexicographic rank and complete `portfolioMetrics`.

- [ ] **Step 1: Add failing tests proving quality, desired scope, preferred family diversity, approach diversity, challenge, and evidence outrank cost; cost and latency break only later ties.**
- [ ] **Step 2: Verify each test fails for the expected missing criterion.**
- [ ] **Step 3: Implement the documented lexicographic rank without a scalar weighted score.**
- [ ] **Step 4: Run focused tests and verify pass.**
- [ ] **Step 5: Commit ranking.**

### Task 5: Decision snapshot, CLI, and malformed-input robustness

**Files:**
- Modify: `tests/test_model_routing_v2.py`
- Modify: `scripts/model_routing/resolve_v2.py`

**Interfaces:**
- Produces: deterministic `decisionSnapshotId`, dispatch phases, degradation flags, compact CLI JSON, and typed failures.

- [ ] **Step 1: Add failing tests for deterministic identifiers, stdin/file CLI, degraded-diversity actions, reroute snapshot changes, and malformed JSON fuzz-smoke.**
- [ ] **Step 2: Verify expected failures.**
- [ ] **Step 3: Implement canonical serialization, decision hashing, phase output, and CLI.**
- [ ] **Step 4: Run focused tests, compilation, and malformed-input fuzz-smoke.**
- [ ] **Step 5: Commit decision and CLI behavior.**

### Task 6: Canonical documentation and integration review

**Files:**
- Create: `docs/model-routing-v2.md`
- Modify: `docs/README.md`
- Verify: `docs/superpowers/specs/2026-09-04-adaptive-model-portfolio-routing-v2-design.md`

**Interfaces:**
- Produces: operator-facing architecture, contract examples, migration rules, and exact verification record.

- [ ] **Step 1: Add failing documentation assertions to the focused test.**
- [ ] **Step 2: Verify failure because the operator document is absent.**
- [ ] **Step 3: Write the operator document and index it without changing Version 1 defaults.**
- [ ] **Step 4: Run focused tests and available repository validators; inspect the final stacked diff.**
- [ ] **Step 5: Open a draft Pull Request stacked on the final Version 1 branch and record exact evidence and remaining full-checkout gates.**

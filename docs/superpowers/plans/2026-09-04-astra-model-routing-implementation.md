# Astra Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task.

**Goal:** Ship a narrow V1 Astra routing skill and a separate full V2 model-routing contract.

**Architecture:** V1 is additive and install-safe. V2 is a pure policy and economics resolver layered above provider realization.

**Tech Stack:** Python 3.11+, JSON, Markdown, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-04-astra-model-routing-design.md`

## Global Constraints

- Do not use GitHub Actions.
- Do not mutate existing V1 native role TOML or its manifest in the quick patch.
- Every route records exact model and effort.
- No silent fallback.
- Maximum effort requires explicit approval.
- Independent review and publication gates remain separate.

### Task 1: Add the V1 skill

- [x] Add one canonical provider-neutral skill body and verify projection-safe structure.
- [x] Add a pure resolver with typed outcomes.
- [x] Add Codex skill metadata.
- [x] Add regression tests and verify RED then GREEN.

### Task 2: Add the V2 contracts

- [x] Add the model catalog.
- [x] Add the dated economics snapshot.
- [x] Add the Version 2 role-routing policy.
- [x] Add the deterministic resolver and regression tests.

### Task 3: Review and publication

- [ ] Run focused and available repository validators locally.
- [ ] Review the final diff for installer ownership and PR overlap.
- [ ] Push V1 and V2 as separate branches/pull requests.
- [ ] Trigger Codex review on each current head.

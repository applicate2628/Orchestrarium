# Astra Model Routing Implementation Plan

> **For agentic workers:** implement each task with test-first development and a fresh review gate.

**Goal:** ship a narrow Version 1 Astra route and a separately reviewable Version 2 model-routing contract.

**Architecture:** Version 1 adds a pure skill-local resolver and does not modify pinned native routing. Version 2 adds strict catalog/policy contracts and a pure router that applies hard gates before complete-route economics.

**Tech Stack:** Python 3.11+, JSON, Markdown, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-04-astra-model-routing-design.md`

## Global constraints

- No GitHub Actions workflow.
- No silent model or effort fallback.
- No automatic Astra fan-out above one.
- No weakening of review, security, QA, or publication gates.
- No claim that a published maximum benchmark result belongs to a specific effort without measured evidence.

## Task 1: Version 1 resolver

- [x] Write failing tests for task defaults, effort evidence, runtime availability, fan-out, and deterministic command-line output.
- [x] Implement the pure resolver and exact Codex flags.
- [x] Verify focused tests.

## Task 2: Version 1 installable skill

- [x] Add provider-neutral skill instructions and Codex metadata.
- [x] Verify the existing canonical skill projection remains the installer owner.
- [x] Keep native role TOML, Version 1 policy, and operator defaults unchanged.

## Task 3: Version 2 contracts

- [ ] Add strict model catalog and role/task policy tests.
- [ ] Separate Luna mechanical execution from Terra/Sol/Astra general capability.
- [ ] Add exact model-local effort floors and migration aliases.

## Task 4: Version 2 route economics

- [ ] Write failing tests for complete candidate sets, per-request long-context pricing, bool rejection, and stale pricing.
- [ ] Implement expected cost and work to an accepted result.
- [ ] Verify Astra can win by reducing calls, output tokens, retries, and rework without bypassing quality floors.

## Task 5: Version 2 selection and migration

- [ ] Add hard availability, maximum-effort, safety, fan-out, fallback, and evidence-independence gates.
- [ ] Add transparent deterministic ranking after hard gates.
- [ ] Map legacy Version 1 `apex-max` to Version 2 `frontier-max`.

## Task 6: Integration and review

- [ ] Run focused and broader available validators.
- [ ] Review PR 4/PR 5 overlap and prospective merge topology.
- [ ] Push separate stacked PRs and trigger `@codex review` on each current head.

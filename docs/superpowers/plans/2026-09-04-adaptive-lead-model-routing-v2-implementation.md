# Adaptive Lead and Model Routing Version 2 — Implementation Plan

> **For agentic workers:** use test-driven development, one bounded artifact per task, and a fresh independent review gate before integration.

**Goal:** migrate Orchestrarium from fixed Version 1 model/provider routing to a provider-neutral logical Lead, dynamic model registry, adaptive role portfolio, structured disagreement workflow, and explicit fallback/diversity evidence.

**Architecture:** preserve the shared governance core and provider packs. Add a Version 2 control plane with exclusive Lead lease, immutable registry/evaluation snapshots, pure route resolver, separate scheduler, provider adapters, artifact normalization, execution-ledger integration, and human-gated degradation handling.

**Documentation contract:** `docs/superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md`

## Global constraints

- Exact model generation numbers appear only in runtime/evaluation snapshots, never stable role policy.
- Codex and Claude are initial Lead Host adapters, not schema enums.
- GLM enters only through Version 2 registry/admission.
- No provider or model output is authorizing.
- Workers remain leaves with zero delegation depth.
- Hard gates and quality requirements precede cost and latency.
- No fallback changes role, scope, mutation, tools, artifact, gate, or independence requirements.
- Existing Version 1 runtime remains usable throughout migration.

## Phase 0: Documentation and machine contracts

**Files:**
- `docs/model-routing-v2/adaptive-routing-contracts.v2.schema.json`
- `docs/model-routing-v2/examples.v2.json`
- `docs/model-routing-v2/README.md`
- `docs/adaptive-model-routing-v2-audit-2026-09-04.md`
- `docs/superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md`
- `tests/test_adaptive_model_routing_v2_contracts.py`

- [x] Write contract tests before creating the Version 2 files.
- [x] Verify the tests fail because the contract surface is absent.
- [x] Define Lead lease, registry snapshot, dispatch, route request, route decision, and worker result schemas.
- [x] Add examples and validate them with Draft 2020-12 JavaScript Object Notation Schema.
- [x] Document adaptive portfolio, structured disagreement, fallback, diversity, and migration boundaries.
- [ ] Run the tests and documentation validators in a full repository checkout.
- [ ] Obtain independent architecture review of the contracts.

## Phase 1: Lead lease and durable ownership

**Planned owners:** persistence/reliability specialist, Lead contract owner, independent reviewer.

- [ ] Write failing tests for one active lease, monotonic epoch, stale-writer fencing, expiry, release, supersession, crash recovery, and host failover.
- [ ] Implement a pure lease reducer and atomic persistence owner.
- [ ] Project the provider-neutral Lead contract into Codex and Claude adapters.
- [ ] Add recovery tooling that revalidates unresolved dispatches after host transfer.
- [ ] Prove that two host adapters cannot concurrently mutate one work item.

## Phase 2: Trusted dynamic registry

**Planned owners:** provider-admission owner, toolchain/security specialist, model-evaluation owner.

- [ ] Write failing tests for arbitrary future provider/model identifiers, unique runtime entries, evidence expiry, model/harness invalidation, and admission regression.
- [ ] Implement immutable registry snapshot generation from trusted provider probes and admission records.
- [ ] Separate availability, entitlement, authentication, containment, admission, capability, and route metrics.
- [ ] Add lineage priors without inherited production admission.
- [ ] Add discovered, shadow, read-only, bounded-write, production, degraded, and quarantined transitions.

## Phase 3: Pure adaptive route resolver

**Planned owners:** routing-policy owner, algorithm specialist, independent architecture reviewer.

- [ ] Write failing tests for complete candidate sets and deterministic decisions from exact snapshots.
- [ ] Implement hard admissibility and quality-floor filters.
- [ ] Implement scope coverage, approach diversity, independence, and evidence-quality comparisons.
- [ ] Implement Pareto filtering within stages and the normative lexicographic order.
- [ ] Compare accepted-result cost and latency only after prior stages.
- [ ] Return selected, degraded, or blocked portfolio decisions with full rejection/fallback evidence.

## Phase 4: Portfolio scheduler and structured disagreement

**Planned owners:** Lead/scheduler owner, provider adapters, evidence owner.

- [ ] Write failing tests for blind proposal isolation, scope-expansion boundaries, named cross-critique targets, and Lead-only synthesis.
- [ ] Launch only `dispatchSpec` instances admitted by the pure resolver.
- [ ] Prevent worker-to-worker task assignment and recursive delegation.
- [ ] Normalize worker artifacts and preserve exact scope/artifact/gate identities.
- [ ] Add empirical arbitration tasks for proofs, tests, benchmarks, and visual evidence.
- [ ] Select extra workers using measured marginal information gain rather than call count alone.

## Phase 5: Fallback, degradation, and provider admission

**Planned owners:** reliability, security, provider-admission, and human-policy owners.

- [ ] Write failing tests for missing subscription, no entitlement, exhausted quota, transient failure, invalid authentication, contract violation, unsafe output, quality failure, and exhausted budget.
- [ ] Allow only explicit same-contract fallback for ordinary availability failures.
- [ ] Require attention or quarantine for authentication and contract failures.
- [ ] Route quality failure to replan/escalation rather than availability fallback.
- [ ] Mark insufficient diversity without inventing independence.
- [ ] Require a human gate for critical degraded-diversity routes.

## Phase 6: Execution ledger migration

**Planned owners:** ledger/persistence owner and backward-compatibility reviewer.

- [ ] Define new ledger events or fields for Lead lease, route request/decision, portfolio slot, snapshots, scope digest, contracts, diversity, and fallback classification.
- [ ] Preserve reads of existing Version 1 event shapes.
- [ ] Refuse to infer missing historical evidence.
- [ ] Add append, replay, recovery, compaction, and corruption tests.
- [ ] Bind scheduler launches and terminals to route decisions and current Lead epochs.

## Phase 7: Provider adapters

**Planned owners:** one adapter owner and one independent security/reliability reviewer per provider.

- [ ] Preserve current Codex and Claude provider behavior through the new dispatch contract.
- [ ] Migrate Kimi only at its independently admitted execution level.
- [ ] Admit Grok only after containment and process-supervision tests pass.
- [ ] Add GLM through the Version 2 registry without a generation number in stable policy.
- [ ] Require exact executable identity, prompt/result bounds, secret controls, timeout, cleanup, and rollback for every adapter.

## Phase 8: Adaptive evidence and NablaCAD evaluation

**Planned owners:** evaluation owner, domain specialists, statistical reviewer.

- [ ] Define task-specific NablaCAD evaluation lanes for mathematics, numerical methods, C++, adapters, kernels, CAD, interface work, tooling, review, and recovery.
- [ ] Record acceptance, post-review defects, scope omissions, successful challenges, tool failures, rework, cost, and latency.
- [ ] Track correlated failures through approach and independence groups.
- [ ] Expire evidence after material model, harness, tool, or repository changes.
- [ ] Keep vendor benchmarks as priors below internal accepted-work evidence.

## Phase 9: Migration and release

- [ ] Map one Version 1 worker route into one Version 2 portfolio slot without semantic widening.
- [ ] Keep legacy model-profile aliases bound to historical meaning.
- [ ] Run full provider-pack, installer, ledger, publication, security, recovery, and end-to-end tests.
- [ ] Perform staged shadow deployment before any production routing default changes.
- [ ] Require human approval for release and rollback readiness.

## Terms and abbreviations

- **CLI — Command-Line Interface:** provider command-line execution surface.
- **GLM — General Language Model:** optional provider lineage admitted only through Version 2.
- **Lead lease:** exclusive ownership record with epoch fencing.
- **Portfolio scheduler:** runtime owner that launches already-resolved worker dispatches.
- **Marginal information gain:** expected new scope, approach, or error class contributed by another worker.
- **Pareto filtering:** removal of candidates dominated on all criteria within one ranking stage.

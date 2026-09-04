# Adaptive Lead and Model Routing Version 2 — Repository Audit

## Contents

1. [Scope](#1-scope)
2. [Established foundations](#2-established-foundations)
3. [Gaps in the current repository](#3-gaps-in-the-current-repository)
4. [Decisions](#4-decisions)
5. [Contract review findings](#5-contract-review-findings)
6. [Version boundary](#6-version-boundary)
7. [Risks and required follow-up](#7-risks-and-required-follow-up)
8. [Verification status](#8-verification-status)
9. [Terms and abbreviations](#9-terms-and-abbreviations)

## 1. Scope

This review covers the shared subagent operating model, Codex and Claude provider packs, the Version 1 role-routing policy, native role bindings, external-worker and external-reviewer contracts, provider prompt transports, Kimi and Grok admission paths, the execution ledger schema, the Astra point route, and the provider-neutral Version 1 Lead/worker route.

The reviewed Version 2 output is intentionally documentation and machine-contract work. It does not claim a working adaptive scheduler or expanded provider admission.

## 2. Established foundations

The repository already provides several correct foundations:

- a shared governance core with provider-specific Codex and Claude projections;
- one main conversation that holds Lead ownership;
- role separation by profession and risk;
- one worker artifact and gate per delegated assignment;
- nonauthorizing external workers and reviewers;
- exact provider prompt transport and execution provenance;
- explicit Kimi read-only admission and Grok containment refusal;
- a durable work-item and execution-ledger model;
- a frozen Version 1 parity baseline before migration.

These foundations support a provider-neutral Lead contract; they should be extended rather than replaced by an unrelated orchestration stack.

## 3. Gaps in the current repository

### 3.1 Lead Host and worker provider are not first-class separate contracts

Codex and Claude provider packs exist, but the stable model does not yet carry an exclusive Lead Host lease, epoch, or provider-neutral host-adapter identity. Without that owner record, failover risks split brain or stale writes.

### 3.2 Model routing is split across static bindings and provider-specific settings

Native role files and Version 1 policy bind current models and effort profiles statically. This is acceptable for the frozen compatibility version but unsuitable for an adaptive future version in which model generations, subscriptions, and measured capability change independently.

### 3.3 The current ledger lacks Version 2 routing identities

`shared/schemas/agent-runs.schema.json` records provider, model, effort, external dispatch, artifact identity, evidence, and terminal authority. It does not first-class represent:

- Lead Host adapter and lease epoch;
- policy, registry, and evaluation snapshots;
- route request and decision;
- portfolio slot and role;
- scope digest;
- artifact and gate contract identifiers;
- diversity status;
- approach and independence groups;
- classified fallback.

Adding these fields requires a separate ledger migration and compatibility tests. Reinterpreting old events would be incorrect.

### 3.4 Provider admission is not a dynamic registry

Version 1 admits a fixed provider set and intentionally constrains Kimi and Grok. There is no generic lifecycle for discovered, shadow, read-only, bounded-write, production, degraded, and quarantined runtimes. GLM has no Version 1 route and must enter only through Version 2 admission.

### 3.5 Previous Version 2 routing was too cost-centric

The earlier design minimized expected cost to acceptance before fully representing scope expansion, independent challenge, approach diversity, structured disagreement, and empirical arbitration. Cost per accepted result remains useful, but only after quality, coverage, and evidence requirements.

### 3.6 Exact model generations were treated as architecture

Current model names are observations, not stable concepts. A policy tying a profession permanently to one numbered model becomes stale as soon as a new generation, effort regime, harness, or provider entitlement changes.

## 4. Decisions

1. Keep one logical Lead contract with provider-specific Lead Host adapters.
2. Enforce one active Lead lease per work item and monotonically increasing epochs.
3. Keep worker providers optional and availabily-aware.
4. Store exact model identity only in immutable registry and execution snapshots.
5. Route stable capability slots, roles, scopes, artifacts, and gates rather than model brands.
6. Build role-specific portfolios for primary proposal, scope expansion, challenge, implementation, review, and visual validation.
7. Run hard gates and quality floors before scope, diversity, evidence, cost, and latency ranking.
8. Treat independent disagreement as a design resource; resolve testable disputes through objective evidence.
9. Report degraded diversity explicitly; critical degradation requires a human gate.
10. Add GLM only in Version 2 through the dynamic registry and provider admission process.
11. Keep Version 1 runtime, policies, adapters, and ledger unchanged in this documentation slice.

## 5. Contract review findings

The Version 2 contract bundle contains six top-level definitions:

- `leadLease`;
- `modelRegistrySnapshot`;
- `dispatchSpec`;
- `routeRequest`;
- `routeDecision`;
- `workerResult`.

The contracts address the reviewed gaps by binding every dispatch to the current Lead lease, policy, registry, and evaluation snapshots; preserving exact role/scope/artifact/gate semantics; keeping provider and model identities dynamic; requiring leaf-only, nonauthorizing workers; carrying diversity and human-gate state; and separating fallback from quality replan and safety quarantine.

The schema cannot alone enforce cross-record uniqueness, lease exclusivity, registry-reference existence, time ordering, capability-score calibration, or candidate-set completeness. Those are runtime validator and persistence-owner responsibilities and remain open implementation work.

## 6. Version boundary

Version 1 remains:

```text
Codex or Claude Lead
  -> one explicit worker
  -> fixed compatibility provider set
  -> no GLM
  -> current provider admission remains authoritative
```

Version 2 introduces:

```text
provider-neutral logical Lead
  -> exclusive host lease
  -> dynamic registry
  -> adaptive worker portfolio
  -> structured disagreement
  -> diversity and evidence policy
  -> GLM and future providers through admission
```

The Version 2 documentation is stacked on the provider-neutral Version 1 route for review continuity, but it does not alter that route's behavior.

## 7. Risks and required follow-up

- **Lease correctness:** requires atomic persistence, fencing by epoch, expiry policy, and crash recovery.
- **Registry trust:** availability, entitlement, executable identity, admission, evidence, and expiry must come from trusted owners rather than repository claims.
- **Adaptive bias:** historical acceptance data can reinforce reviewer or benchmark bias; evidence sources and confidence must remain visible.
- **False diversity:** different models may share correlated failure modes; provider family alone is insufficient.
- **Scope growth:** scope expansion must return an artifact to Lead, not silently mutate the admitted work item.
- **Cost estimation:** forecast cost cannot override hard gates and must be marked separately from measured cost.
- **Provider fallback:** authentication and contract failures require attention or quarantine, not blind retries.
- **Ledger migration:** new fields must preserve backward reads and cannot invent evidence for historical events.
- **Adapter work:** Kimi, Grok, GLM, and future providers require independent containment and admission work before write use.

## 8. Verification status

The documentation-stage acceptance requires:

- valid Draft 2020-12 schema;
- examples validating against all contracts;
- no model generation numbers in stable schema or normative design;
- explicit quality/scope/challenge-before-cost order;
- explicit degraded diversity and human gate;
- exact separation of Lead Host, worker runtime, provider family, model identity, and effort;
- no runtime or Version 1 policy modification.

Runtime verification, ledger migration, provider admission, scheduler tests, crash recovery, and end-to-end provider execution remain open by design.

## 9. Terms and abbreviations

- **CLI — Command-Line Interface:** command-line provider execution surface.
- **GLM — General Language Model:** provider lineage introduced only through the Version 2 registry.
- **Lead lease:** exclusive epoch-numbered ownership record for the logical Lead.
- **Split brain:** two hosts concurrently acting as Lead for one work item.
- **Capability slot:** stable task ability independent of model identity.
- **Admission:** verified permission for a runtime to perform a class of execution.
- **Scope expansion:** bounded search for omitted factors and alternatives without silently changing task ownership.
- **Empirical arbitration:** resolving a model disagreement using objective evidence.

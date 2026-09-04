# Adaptive Lead and Model Routing — Orchestrarium Version 2

**Status:** documentation and machine-contract draft. These files do not change the installed Version 1 runtime, launch a provider, grant provider admission, or migrate the execution ledger.

## Contents

1. [Purpose](#1-purpose)
2. [Stable architecture](#2-stable-architecture)
3. [Dynamic model registry](#3-dynamic-model-registry)
4. [Adaptive portfolio routing](#4-adaptive-portfolio-routing)
5. [Fallback and Lead continuity](#5-fallback-and-lead-continuity)
6. [Files in this surface](#6-files-in-this-surface)
7. [Migration boundary](#7-migration-boundary)
8. [Terms and abbreviations](#8-terms-and-abbreviations)

## 1. Purpose

Orchestrarium Version 2 separates the persistent logical Lead from any particular vendor or model generation. A Codex or Claude adapter may host the Lead today; another admitted Lead adapter may do so later without changing the Lead contract. Optional Command-Line Interface (CLI) workers form a replaceable pool whose members may be configured, unconfigured, paid, unpaid, quota-exhausted, temporarily unavailable, degraded, or quarantined.

The router does not seek only the cheapest model call. It constructs an admissible portfolio that first satisfies correctness and quality floors, then broadens scope, adds genuinely different approaches, provides independent challenge, and produces verifiable evidence. Accepted-result cost and latency are tie-break criteria after those requirements.

## 2. Stable architecture

The stable policy names responsibilities rather than model products:

```text
provider-neutral Lead contract
  -> exclusive Lead lease
  -> adaptive portfolio router
  -> provider adapters
  -> nonauthorizing leaf workers
  -> evidence and review gates
  -> Lead synthesis
  -> human merge/release policy
```

The stable invariants are:

- exactly one active logical Lead owns a work item;
- the active Lead is represented by an exclusive lease with a monotonically increasing epoch;
- Lead Host adapter, worker runtime, provider family, lineage, exact model identity, and effort are separate facts;
- one worker receives one role, one bounded scope, one artifact contract, and one gate contract;
- a worker cannot delegate recursively or authorize acceptance, merge, release, publication, or Lead transfer;
- a worker result is a claim and an artifact, not accepted proof;
- no fallback may silently change role, scope, tools, mutation rights, artifact, gate, or independence requirements.

## 3. Dynamic model registry

Exact model identifiers live only in an immutable runtime registry snapshot. Stable policy contains no model generation numbers and no permanent claim that one lineage is universally best.

Each registry entry records:

- provider adapter and runtime identity;
- provider family, model lineage, and runtime-observed model identity;
- Lead and worker capability;
- availability and entitlement state;
- admission state and mutation ceiling;
- supported and admitted effort values;
- tools and capability evidence;
- approach tags and independence groups;
- evidence freshness;
- expected accepted-result cost, calls, rework, and latency.

A new Kimi, Grok, GLM, Codex-line, Claude-line, or future model may inherit only a lineage prior. It does not inherit production admission or benchmark results automatically. It progresses through observed admission states such as `discovered`, `shadow`, `read-only`, `bounded-write`, and `production`; regressions may move it to `degraded` or `quarantined`.

## 4. Adaptive portfolio routing

The router selects role-specific portfolio slots rather than one global winner. Stable portfolio roles include:

- `primary` — proposes the main solution;
- `scope-expander` — searches for missed factors, adjacent alternatives, and hidden assumptions;
- `challenger` — attempts to falsify the primary proposal;
- `implementer` — converts an accepted design into a bounded implementation artifact;
- `reviewer` — independently checks the integrated result;
- `visual-validator` — checks visual, document, or interface states.

The required selection order is:

```text
hard admissibility
  -> quality floor
  -> scope coverage
  -> independent challenge
  -> evidence quality
  -> accepted-result cost
  -> latency
  -> stable identifier
```

This is a lexicographic decision after hard gates, not a single scalar score. A lower price cannot compensate for a missing critical capability, stale evidence, an unmet quality floor, or falsely claimed model diversity.

For complex work, the recommended flow is independent initial proposals, explicit scope expansion, controlled cross-model critique, Lead synthesis, and empirical arbitration. The router should prefer the next worker that is expected to add new information, not merely another similar answer.

## 5. Fallback and Lead continuity

A worker provider being absent or unpaid is ordinary scheduler input. `not-configured`, `not-entitled`, `quota-exhausted`, temporary transport failure, and ordinary unavailability may advance to the next explicit candidate. Authentication failure, contract violation, unsafe output, and quality failure have different dispositions and must not be collapsed into one retry loop.

The logical Lead may survive a host change. A Lead Host transfer requires a new exclusive lease epoch, durable work-item state, and revalidation of outstanding dispatches. Two Lead Hosts may not mutate orchestration state concurrently.

Diversity is preferred but not fabricated. When fewer independent provider families are available than requested, the route reports `degraded`; critical work requires the human gate specified by policy instead of pretending that several models from one family are independent.

## 6. Files in this surface

- [`adaptive-routing-contracts.v2.schema.json`](adaptive-routing-contracts.v2.schema.json) — Draft 2020-12 JavaScript Object Notation Schema bundle for Lead lease, registry snapshot, route request, dispatch, route decision, and worker result.
- [`examples.v2.json`](examples.v2.json) — nonauthorizing examples that validate against the contract bundle.
- [`../adaptive-model-routing-v2-audit-2026-09-04.md`](../adaptive-model-routing-v2-audit-2026-09-04.md) — repository review and identified migration gaps.
- [`../superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md`](../superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md) — normative design specification.
- [`../superpowers/plans/2026-09-04-adaptive-lead-model-routing-v2-implementation.md`](../superpowers/plans/2026-09-04-adaptive-lead-model-routing-v2-implementation.md) — implementation plan; runtime tasks remain open.

## 7. Migration boundary

This surface is intentionally separate from Version 1. Version 1 retains its fixed compatibility provider set and one-worker resolver. GLM enters only through the Version 2 dynamic registry. Existing provider adapters, role taxonomy, `agents-mode`, native role files, and `agent-runs.jsonl` remain unchanged until their dedicated migration tasks pass tests and review.

The Version 1 dispatch may migrate into one Version 2 portfolio slot only when role, scope, capability, mutation class, required tools, provider-family exclusions, artifact contract, gate contract, and nonauthorizing authority are preserved exactly.

## 8. Terms and abbreviations

- **CLI — Command-Line Interface:** command-line execution surface for a provider worker.
- **Lead Host adapter:** provider-specific implementation of the stable logical Lead contract.
- **Lead lease:** exclusive, epoch-numbered ownership record preventing two active Leads from mutating one work item.
- **Model registry snapshot:** immutable observation of available runtimes, models, admission, evidence, and route metrics.
- **Capability slot:** stable required ability independent of a model name.
- **Model portfolio:** set of workers assigned different roles in one routed task.
- **Admission:** verified permission for a runtime to perform a class of work or mutation.
- **Fallback:** explicit move to a later admitted candidate after a classified failure.
- **Empirical arbitration:** resolution of a disagreement through tests, measurements, proofs, or other objective evidence.

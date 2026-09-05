# Adaptive Lead and Model Routing — Orchestrarium Version 2

**Status:** documentation and machine-contract draft. These files do not change the installed Version 1 runtime, launch a provider, grant provider admission, or migrate the execution ledger.

## Contents

1. [Purpose](#1-purpose)
2. [Stable architecture](#2-stable-architecture)
3. [Dynamic model registry](#3-dynamic-model-registry)
4. [Adaptive portfolio routing](#4-adaptive-portfolio-routing)
5. [Operational execution boundary](#5-operational-execution-boundary)
6. [Fallback and Lead continuity](#6-fallback-and-lead-continuity)
7. [Files in this surface](#7-files-in-this-surface)
8. [Migration boundary](#8-migration-boundary)
9. [Terms and abbreviations](#9-terms-and-abbreviations)

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
- Lead Host adapter, worker runtime, provider family, lineage, exact model identity, effort, and orchestration mode are separate facts;
- one worker receives one role, one bounded scope, one artifact contract, and one gate contract;
- a worker cannot delegate recursively or authorize acceptance, merge, release, publication, or Lead transfer;
- a worker result is a claim and an artifact, not accepted proof;
- no fallback may silently change role, scope, tools, mutation rights, artifact, gate, data policy, quality floor, or independence requirements.

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

This is a lexicographic decision after hard gates, not a single scalar score. A lower price cannot compensate for a missing critical capability, stale evidence, an unmet quality floor, forbidden data egress, or falsely claimed model diversity.

For complex work, the recommended flow is independent initial proposals, explicit scope expansion, controlled cross-model critique, Lead synthesis, and empirical arbitration. The router should prefer the next worker that is expected to add new information, not merely another similar answer.

Capability, effort, and orchestration are independent axes. Each portfolio slot has a provider-neutral effort intent and quality floor. A provider adapter records how that intent maps to its concrete runtime setting; an inability to expose a higher setting does not waive the quality floor. A provider-native internal multi-agent mode is separately admitted and never inferred from effort.

## 5. Operational execution boundary

The two schema bundles have different owners:

```text
adaptive-routing-contracts.v2.schema.json
  = semantic routing records

adaptive-routing-operational.v2.schema.json
  = execution, fencing, egress, budget, retry, settlement, and feedback envelopes
```

The operational layer requires:

- a self-contained Lead fence with lease, epoch, holder, trusted snapshot identifiers and digests, digest profile, and expiry observation;
- a verified-complete candidate-set digest and evidence reference;
- provider policy for family, region, retention, sensitive source code, external web access, and secret exclusion;
- hard portfolio, parallelism, call, attempt, prompt-byte, result-byte, time, and accepted-result-cost budgets;
- slot-specific effort intent and evidence-backed provider mapping;
- isolated write boundaries with precondition, allowed-path, rollback, commit, and destructive-operation policy;
- cancellation, process supervision, terminal receipts, and idempotent attempts;
- typed fallback, rejection, contradiction, and human-gate records;
- a terminal result envelope bound to the exact dispatch attempt and Lead fence;
- a nonauthorizing route outcome bound to the selected portfolio and objective evidence.

Both schema bundles require whitespace-free identifiers, Secure Hash Algorithm 256-bit (SHA-256) digest fields, and Coordinated Universal Time (UTC) timestamp fields. A trailing line break is rejected, not trimmed or silently normalized into another identity. Existing alphabet, length, uppercase UTC spelling, and fractional-second constraints still apply. Timestamp validation must also enable the date-time format checker to reject impossible calendar dates. These local field checks do not compute digests, bind separate records, or grant runtime admission.

The operational schema does not implement a second router. A future cross-record validator validates the core records and their operational envelopes together, then a scheduler executes only admitted dispatches.

Detailed findings, implementation order, and explicitly rejected overengineering are recorded in [`deep-review-operational-hardening.md`](deep-review-operational-hardening.md).

### Validating one declared record

These files are **definition bundles**, not root-level record validators. Their
`$defs` entries are inert until a caller selects the expected definition through
`$ref`. Passing an instance to a bundle root can accept even an empty object;
checking that the bundle is a valid schema checks the schema, not the instance.

After trusted acquisition, the consuming owner chooses the expected record type
from its own contract, never from an untrusted record's claim. This example uses
the same local-reference pattern as the tests and enables calendar-format checks:

```python
from jsonschema import Draft202012Validator, FormatChecker


def validate_record(bundle: dict, expected_definition: str, record: object) -> None:
    if expected_definition not in bundle["$defs"]:
        raise ValueError("unknown record definition")
    wrapper = {
        "$schema": bundle["$schema"],
        "$defs": bundle["$defs"],
        "$ref": f"#/$defs/{expected_definition}",
    }
    checker = FormatChecker()
    if "date-time" not in checker.checkers:
        raise RuntimeError("date-time format checker is unavailable")
    Draft202012Validator.check_schema(wrapper)
    Draft202012Validator(wrapper, format_checker=checker).validate(record)
```

For example, use `leadLease` with the semantic bundle and `dispatchControl` with
the operational bundle. An unknown definition is an error, not a fallback to root
validation. The already acquired bundle is trusted input here; this snippet does
not replace the bounded, duplicate-key-rejecting reader required by
[runtime validation obligations](runtime-validation-obligations.md#4-snapshot-and-digest-trust).
The environment must supply the `date-time` checker and its optional dependency;
merely constructing `FormatChecker()` does not establish that this check exists.
The example refuses a missing checker instead of accepting unchecked dates.
It validates local record shape only, not cross-record consistency, admission, or
authority to launch. The snippet is tested directly from this guide.

## 6. Fallback and Lead continuity

A worker provider being absent or unpaid is ordinary scheduler input. `not-configured`, `not-entitled`, `quota-exhausted`, temporary transport failure, and ordinary unavailability may advance to the next explicit candidate. Authentication failure, contract violation, unsafe output, quality failure, budget exhaustion, and stale-fence results have different dispositions and must not be collapsed into one retry loop.

The logical Lead may survive a host change. A Lead Host transfer requires a new exclusive lease epoch, durable work-item state, cancellation or revalidation of outstanding dispatches, and a fencing check before any terminal result can enter synthesis. Two Lead Hosts may not mutate orchestration state concurrently.

Diversity is preferred but not fabricated. When fewer independent provider families or approach groups are available than requested, the route reports `degraded`; critical work requires the human gate specified by policy instead of pretending that several models from one family are independent.

## 7. Files in this surface

The two example files illustrate individual record shapes, not one cross-record-consistent executable stage trace. Schema success alone does not establish matching ownership, real digest contents, stage readiness, or provider admission; use the runtime handoff documents below for the separate obligations.

### Core contracts

- [`adaptive-routing-contracts.v2.schema.json`](adaptive-routing-contracts.v2.schema.json) — Draft 2020-12 JavaScript Object Notation Schema bundle for Lead lease, registry snapshot, route request, dispatch, route decision, and worker result.
- [`examples.v2.json`](examples.v2.json) — nonauthorizing examples that validate against the core bundle.

### Operational hardening

- [`adaptive-routing-operational.v2.schema.json`](adaptive-routing-operational.v2.schema.json) — operational envelopes for fencing, effort mapping, data policy, budgets, write safety, fallback, process settlement, contradictions, and routing outcomes.
- [`operational-examples.v2.json`](operational-examples.v2.json) — validating operational examples.
- [`deep-review-operational-hardening.md`](deep-review-operational-hardening.md) — deep-review findings, cross-record obligations, implementation order, and non-goals.

### Review and implementation documents

- [`runtime-validation-obligations.md`](runtime-validation-obligations.md) — future cross-record, ownership, input-stage, admission, and result-verification obligations; not implemented runtime enforcement.
- [`review-loop-closure.md`](review-loop-closure.md) — review conclusions, safe implementation slices, and deliberately deferred mechanisms.
- [`../adaptive-model-routing-v2-audit-2026-09-04.md`](../adaptive-model-routing-v2-audit-2026-09-04.md) — repository review and identified migration gaps.
- [`../superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md`](../superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md) — normative design specification.
- [`../superpowers/plans/2026-09-04-adaptive-lead-model-routing-v2-implementation.md`](../superpowers/plans/2026-09-04-adaptive-lead-model-routing-v2-implementation.md) — implementation plan; runtime tasks remain open.

## 8. Migration boundary

This surface is intentionally separate from Version 1. Version 1 retains its fixed compatibility provider set and one-worker resolver. GLM enters only through the Version 2 dynamic registry. Existing provider adapters, role taxonomy, `agents-mode`, native role files, and `agent-runs.jsonl` remain unchanged until their dedicated migration tasks pass tests and review.

The Version 1 dispatch may migrate into one Version 2 portfolio slot only when role, scope, capability, mutation class, required tools, provider-family exclusions, artifact contract, gate contract, nonauthorizing authority, and request fingerprint provenance are preserved. The Version 2 owner then adds trusted snapshot digests, a Lead fence, slot effort intent, data policy, resource budget, and execution envelope; it must not invent these facts for historical V1 events.

## 9. Terms and abbreviations

- **Definition bundle:** a library of schema definitions under `$defs`; a caller applies an expected definition through `$ref`.
- **Record validation:** checking one acquired record against its expected schema, without claiming execution admission.
- **CLI — Command-Line Interface:** command-line execution surface for a provider worker.
- **Lead Host adapter:** provider-specific implementation of the stable logical Lead contract.
- **Lead lease:** exclusive, epoch-numbered ownership record preventing two active Leads from mutating one work item.
- **Lead fence:** self-contained lease, epoch, holder, snapshot, and digest binding used to reject stale work.
- **Model registry snapshot:** immutable observation of available runtimes, models, admission, evidence, and route metrics.
- **Capability slot:** stable required ability independent of a model name.
- **Model portfolio:** set of workers assigned different roles in one routed task.
- **Effort intent:** provider-neutral requested reasoning depth for one portfolio slot.
- **Admission:** verified permission for a runtime to perform a class of work or mutation.
- **Fallback:** explicit move to a later admitted candidate after a classified failure.
- **Terminal receipt:** trusted terminal-state evidence appropriate to local-process, in-process, or remote-job execution.
- **Empirical arbitration:** resolution of a disagreement through tests, measurements, proofs, or other objective evidence.

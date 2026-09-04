# Provider-Neutral Lead and Worker Routing — Version 1 Design

## Contents

1. [Goal](#1-goal)
2. [Constraints](#2-constraints)
3. [Architecture](#3-architecture)
4. [Resolver contract](#4-resolver-contract)
5. [Fallback semantics](#5-fallback-semantics)
6. [Safety and authority](#6-safety-and-authority)
7. [Version 1 provider scope](#7-version-1-provider-scope)
8. [Testing](#8-testing)
9. [Migration to Version 2](#9-migration-to-version-2)
10. [Terms and abbreviations](#10-terms-and-abbreviations)

## 1. Goal

Add an immediately usable, additive Orchestrarium Version 1 routing surface in which one logical Lead is hosted by either Codex or Claude, while eligible CLI workers are selected from an explicitly supplied, optional provider pool. A missing subscription, unavailable CLI, exhausted quota, or disabled provider is normal routing input rather than a failure of the Lead workflow.

## 2. Constraints

- Do not modify `shared/role-routing-policy.v1.json`, native role TOML, the native role manifest, `agents-mode` defaults, or the frozen Version 1 parity baseline.
- Keep the existing Astra point route intact and independently reviewable.
- Do not add GLM to Version 1.
- Do not make Kimi or Grok writable merely because the resolver can represent them; actual execution remains limited by the existing provider admission and containment contracts.
- Do not silently fall back to an ambient provider, model, effort, or runtime default.
- Do not let a worker authorize acceptance, merge, release, publication, or Lead transfer.
- Do not recursively delegate from a worker.

## 3. Architecture

Version 1 adds a provider-neutral `lead-worker-routing` skill with a pure resolver. The resolver does not launch a process, inspect credentials, mutate configuration, or write repository state. It consumes one exact request and returns either one exact nonauthorizing worker route or a typed non-success decision.

```text
Logical Lead Contract
  ├── Codex Lead Host
  └── Claude Lead Host
          │
          ▼
Pure Version 1 worker resolver
          │
          ├── Codex CLI/native isolated worker
          ├── Claude CLI isolated worker
          ├── Kimi CLI worker, only at its admitted mutation level
          └── Grok CLI worker, only when containment is admitted
```

The Lead Host and worker runtime are separate facts. A Codex-hosted Lead may select a Claude, Kimi, Grok, or explicitly isolated Codex worker. A Claude-hosted Lead may select a Codex, Kimi, Grok, or explicitly isolated Claude worker.

## 4. Resolver contract

The Python API is:

```python
resolve_v1_worker_route(request: dict[str, object]) -> dict[str, object]
```

The request has these exact top-level fields:

```json
{
  "schemaVersion": 1,
  "leadHost": "codex",
  "capabilitySlot": "engineering-challenge",
  "mutationClass": "read-only",
  "requiredTools": [],
  "candidates": []
}
```

Each candidate has these exact fields:

```json
{
  "candidateId": "grok-review-1",
  "provider": "grok",
  "runtime": "grok-cli",
  "providerFamily": "xai",
  "model": "runtime-observed-model",
  "effort": "high",
  "priority": 10,
  "availability": "available",
  "maxMutationClass": "read-only",
  "capabilities": ["engineering-challenge"],
  "tools": [],
  "isolatedFromLead": true,
  "maxDelegationDepth": 0,
  "authorizing": false
}
```

`capabilitySlot` is a stable capability name, not a model name. `model` is runtime-observed provenance and may change without changing the resolver. `priority` is supplied by the current operator policy or measured routing snapshot; Version 1 does not embed one universal vendor order.

The command-line interface reads one UTF-8 JSON request from `--request-file <path>` or standard input when `--request-file -` is used. Output is one deterministic compact JSON object.

## 5. Fallback semantics

The resolver evaluates candidates by ascending `priority`, then `candidateId`. It rejects or skips candidates that:

- belong to a provider not admitted in Version 1;
- are not `available`;
- do not advertise the required capability;
- cannot satisfy the requested mutation class;
- lack a required tool;
- are not isolated from the active Lead when they use the same provider;
- have nonzero delegation depth;
- claim authorizing authority.

The first fully admitted candidate is selected. If an earlier-ranked candidate was otherwise suitable but unavailable, the decision records an explicit fallback event with the skipped candidate and stable reason. If no candidate is selectable, the resolver returns a typed `unavailable` or `denied` result and no worker route.

Availability values are:

```text
available
not-configured
not-entitled
quota-exhausted
temporary-transport-failure
auth-invalid
contract-violation
unavailable
```

`not-configured`, `not-entitled`, `quota-exhausted`, `temporary-transport-failure`, and `unavailable` permit selection of a later explicit candidate. `auth-invalid` and `contract-violation` are recorded as hard provider failures; they never authorize use of that candidate's output.

## 6. Safety and authority

Every selected route has:

```text
authorizing = false
maxDelegationDepth = 0
fallback = explicit-candidate-order only
```

The resolver never transfers the Lead lease. The Lead verifies the returned artifact, diff, logs, test output, and gate evidence before forwarding or accepting it. Same-family or same-provider workers may be useful, but they do not count as independent provider review.

## 7. Version 1 provider scope

Version 1 admits exactly these provider identifiers in the resolver contract:

```text
codex
claude
kimi
grok
```

This is a compatibility boundary, not a permanent vendor list. GLM and future providers enter through Version 2's dynamic registry. Existing execution restrictions remain authoritative: representing Kimi or Grok as a candidate does not bypass their current read-only or unavailable execution states.

## 8. Testing

Focused tests must prove:

- only Codex and Claude can host the Lead;
- provider and model identity are separate;
- arbitrary runtime-observed model identifiers are accepted;
- an unpaid or quota-exhausted first candidate falls back to the next admitted candidate;
- same-host recursion is denied unless the worker is explicitly isolated;
- mutation and tool requirements are enforced;
- Kimi and Grok do not gain write authority from routing metadata;
- GLM is rejected in Version 1;
- no worker can be authorizing or delegate recursively;
- input and output are deterministic and strict;
- the CLI returns nonzero for denied or unavailable decisions.

## 9. Migration to Version 2

Version 2 supersedes the fixed Version 1 provider set with a dynamic registry and selects a portfolio of role-specific workers rather than a single worker. The Version 1 request can migrate into one Version 2 portfolio slot without changing its capability, mutation, tool, authority, or artifact constraints.

## 10. Terms and abbreviations

- **CLI — Command-Line Interface:** provider command-line runtime used for a worker invocation.
- **Lead Host:** Codex or Claude runtime holding the logical Lead role and durable orchestration state.
- **Capability slot:** stable task ability required from a worker, independent of model naming.
- **Fallback:** explicit selection of a later admitted candidate after an earlier candidate is unavailable.
- **Admission:** verified permission for a runtime to perform a class of work or mutation.
- **Provenance:** exact record of the selected provider, runtime, model, effort, and decision basis.

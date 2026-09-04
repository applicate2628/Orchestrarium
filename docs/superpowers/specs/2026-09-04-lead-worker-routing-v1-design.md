# Provider-Neutral Lead and Worker Routing — Version 1 Design

## Contents

1. [Goal](#1-goal)
2. [Constraints](#2-constraints)
3. [Architecture](#3-architecture)
4. [Resolver contract](#4-resolver-contract)
5. [Candidate admission](#5-candidate-admission)
6. [Fallback semantics](#6-fallback-semantics)
7. [Safety, authority, and evidence](#7-safety-authority-and-evidence)
8. [Command-line input](#8-command-line-input)
9. [Version 1 provider scope](#9-version-1-provider-scope)
10. [Testing](#10-testing)
11. [Migration to Version 2](#11-migration-to-version-2)
12. [Terms and abbreviations](#12-terms-and-abbreviations)

## 1. Goal

Add an immediately usable, additive Orchestrarium Version 1 routing surface in which one logical Lead is hosted by either Codex or Claude, while one bounded Command-Line Interface (CLI) worker is selected from an explicitly supplied optional provider pool. A missing subscription, unavailable CLI, exhausted quota, or disabled provider is normal routing input rather than a failure of the Lead workflow.

The route must preserve the same assigned role, bounded scope, artifact contract, gate contract, tool requirements, mutation class, and review-independence requirement when it falls back from one provider to another. Interchangeability means a common contract and explicit fallback; it does not mean equal competence or equal execution authority.

## 2. Constraints

- Do not modify `shared/role-routing-policy.v1.json`, native role Tom's Obvious Minimal Language (TOML) files, the native role manifest, `agents-mode` defaults, or the frozen Version 1 parity baseline.
- Keep the existing Astra point route intact and independently reviewable.
- Do not add General Language Model (GLM) providers to Version 1.
- Do not make Kimi or Grok writable merely because the resolver can represent them; actual execution remains limited by existing provider admission and containment contracts.
- Do not silently fall back to an ambient provider, model, effort, runtime, role, scope, artifact, gate, or tool set.
- Do not let a worker authorize acceptance, merge, release, publication, or Lead transfer.
- Do not recursively delegate from a worker.
- Do not treat caller-declared provider family or runtime identity as freely spoofable metadata.

## 3. Architecture

Version 1 adds a provider-neutral `lead-worker-routing` skill with a pure resolver. The resolver does not launch a process, inspect credentials, mutate configuration, grant provider admission, or write repository state. It consumes one exact request and returns either one exact nonauthorizing worker route or a typed non-success decision.

```text
Logical Lead Contract
  ├── Codex Lead Host
  └── Claude Lead Host
          │
          ▼
Pure Version 1 worker resolver
          │
          ├── Codex CLI/native isolated worker
          ├── Claude CLI/native isolated worker
          ├── Kimi CLI worker, only at its admitted mutation level
          └── Grok CLI worker, only when containment is admitted
```

The Lead Host and worker runtime are separate facts. A Codex-hosted Lead may select a Claude, Kimi, Grok, or explicitly isolated Codex worker. A Claude-hosted Lead may select a Codex, Kimi, Grok, or explicitly isolated Claude worker.

## 4. Resolver contract

The Python interface is:

```python
resolve_v1_worker_route(request: dict[str, object]) -> dict[str, object]
```

The request has these exact top-level fields:

```json
{
  "schemaVersion": 1,
  "dispatchId": "dispatch-2026-09-04-001",
  "policySnapshotId": "policy-snapshot-001",
  "leadHost": "codex",
  "assignedRole": "engineering-challenger",
  "scopeId": "scope-kernel-layout-001",
  "capabilitySlot": "engineering-challenge",
  "mutationClass": "read-only",
  "requiredTools": [],
  "excludedProviderFamilies": ["openai"],
  "artifactContract": "challenge-report-v1",
  "gateContract": "lead-verifies-artifact-v1",
  "candidates": []
}
```

The identity fields bind the decision to one dispatch, policy snapshot, role, scope, artifact, and gate. `excludedProviderFamilies` lets a review lane require evidence from a different provider family than the author. An empty list means that the caller does not require provider-family independence for this one worker route.

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
  "authorizing": false,
  "evidenceSnapshotId": "runtime-evidence-001"
}
```

`capabilitySlot` is a stable capability name, not a model name. `model` is runtime-observed provenance and may change without changing the resolver. `priority` is supplied by the current operator policy or measured routing snapshot; Version 1 does not embed one universal vendor order. `evidenceSnapshotId` binds the candidate's availability, model, effort, runtime, and admission observations to caller-owned evidence without making the resolver a probe owner.

A selected decision repeats the dispatch, policy, role, scope, capability, mutation, tool, independence, artifact, and gate fields. Fallback therefore changes only the selected worker realization.

## 5. Candidate admission

The resolver rejects a candidate that:

- belongs to a provider not admitted in Version 1;
- supplies a provider family inconsistent with its provider identity;
- supplies a runtime inconsistent with the admitted provider runtime set;
- belongs to a provider family excluded by the request;
- lacks the required capability or tool;
- cannot satisfy the requested mutation class;
- exceeds the Version 1 provider mutation ceiling;
- is not isolated from an active Lead of the same provider;
- has nonzero delegation depth;
- claims authorizing authority.

The provider/runtime mapping admitted by this compatibility resolver is:

```text
codex  -> codex-cli | codex-native
claude -> claude-cli | claude-native
kimi   -> kimi-cli
grok   -> grok-cli
```

The mapping prevents route metadata from relabeling one execution surface as another. It does not prove that the executable is installed or trusted; the provider adapter remains responsible for executable identity and containment.

## 6. Fallback semantics

The resolver evaluates candidates by ascending `priority`, then `candidateId`. The first fully admitted and available candidate is selected.

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

`not-configured`, `not-entitled`, `quota-exhausted`, `temporary-transport-failure`, and `unavailable` are classified as `availability-fallback`. `auth-invalid` and `contract-violation` are classified as `provider-hard-failure`. A later explicit candidate may still be selected because no output from the failed candidate is accepted, but the final decision sets:

```text
hardFailureObserved = true
requiresOperatorAttention = true
```

Every fallback event records candidate identity, provider, evidence snapshot, availability, stable error identifier, and failure class. If no candidate is selectable, the resolver returns a typed `unavailable` or `denied` result and no worker route.

## 7. Safety, authority, and evidence

Every selected route has:

```text
authorizing = false
maxDelegationDepth = 0
requiresLeadVerification = true
fallbackPolicy = explicit-candidate-order
```

The resolver never transfers the Lead role or lease. The Lead verifies the returned artifact, diff, logs, test output, and gate evidence before forwarding or accepting it. Same-family or same-provider workers may be useful, but they do not count as independent provider review. The caller uses `excludedProviderFamilies` when independence is required.

`policySnapshotId` and candidate `evidenceSnapshotId` are references, not signatures. Version 1 binds them into the deterministic decision but does not validate the external evidence store. Version 2 owns a first-class signed or hash-bound evidence registry.

## 8. Command-line input

The command-line interface reads one UTF-8 JavaScript Object Notation (JSON) request from:

```text
--request-file <ordinary-file>
--request-file -
```

`-` means standard input. A request file must be a stable ordinary file. Symbolic links, reparse points, non-regular files, file replacement during reading, and requests larger than 1 mebibyte fail closed. Process substitution and named pipes are intentionally not request-file inputs; use standard input instead.

The parser rejects duplicate keys at any JSON object depth. Output is one deterministic compact JSON object. Selected results exit with code `0`; denied, unavailable, malformed, duplicate-key, unsafe-file, and oversized requests exit with code `2`.

## 9. Version 1 provider scope

Version 1 admits exactly these provider identifiers in the resolver contract:

```text
codex
claude
kimi
grok
```

This is a compatibility boundary, not a permanent vendor list. GLM and future providers enter through Version 2's dynamic registry. Existing execution restrictions remain authoritative: representing Kimi or Grok as a candidate does not bypass their current read-only or unavailable execution states.

## 10. Testing

Focused tests must prove:

- only Codex and Claude can host the Lead;
- provider, runtime, provider family, and model identity remain distinct;
- the decision preserves role, scope, policy snapshot, artifact, and gate contracts;
- arbitrary runtime-observed model identifiers are accepted;
- an unpaid or quota-exhausted first candidate falls back to the next admitted candidate;
- hard provider failures remain visible after fallback;
- a different provider family can be required for independent review;
- same-host recursion is denied unless the worker is explicitly isolated;
- mutation and tool requirements are enforced;
- Kimi and Grok do not gain write authority from routing metadata;
- GLM is rejected in Version 1;
- no worker can be authorizing or delegate recursively;
- duplicate JSON keys, symbolic-link request files, and oversized requests fail closed;
- input and output are deterministic and strict;
- the CLI returns nonzero for denied or unavailable decisions.

## 11. Migration to Version 2

Version 2 supersedes the fixed Version 1 provider set with a dynamic registry and selects a portfolio of role-specific workers rather than a single worker. The Version 1 request can migrate into one Version 2 portfolio slot without changing its role, scope, capability, mutation, tool, independence, authority, artifact, or gate constraints.

Version 2 must not hardcode generation numbers into stable routing policy. Exact model identifiers live in runtime snapshots; stable policy refers to capability slots, admission levels, evidence freshness, quality floors, diversity requirements, accepted-result cost, and latency.

## 12. Terms and abbreviations

- **CLI — Command-Line Interface:** provider command-line runtime used for a worker invocation.
- **JSON — JavaScript Object Notation:** serialized request and decision format.
- **Lead Host:** Codex or Claude runtime holding the logical Lead role and durable orchestration state.
- **Capability slot:** stable task ability required from a worker, independent of model naming.
- **Fallback:** explicit selection of a later admitted candidate after an earlier candidate is unavailable.
- **Admission:** verified permission for a runtime to perform a class of work or mutation.
- **Provenance:** exact record of the selected provider, runtime, model, effort, evidence snapshot, and decision basis.
- **Artifact contract:** identifier of the required worker output structure.
- **Gate contract:** identifier of the verification required before the artifact may advance.

# Provider-Neutral Lead and Worker Routing — Version 1 Design

## Contents

1. [Decision](#1-decision)
2. [Compatibility constraints](#2-compatibility-constraints)
3. [Architecture](#3-architecture)
4. [Request and decision contract](#4-request-and-decision-contract)
5. [Candidate admission](#5-candidate-admission)
6. [Fallback semantics](#6-fallback-semantics)
7. [Request identity and execution authority](#7-request-identity-and-execution-authority)
8. [Strict command-line input](#8-strict-command-line-input)
9. [Review conclusions and non-goals](#9-review-conclusions-and-non-goals)
10. [Testing](#10-testing)
11. [Migration to Version 2](#11-migration-to-version-2)
12. [Terms and abbreviations](#12-terms-and-abbreviations)

## 1. Decision

Orchestrarium Version 1 adds one provider-neutral routing surface in which a logical Lead is hosted by Codex or Claude and selects one bounded optional Command-Line Interface (CLI) worker from explicit Codex, Claude, Kimi, or Grok candidates. Missing configuration, entitlement, quota, or temporary availability is normal routing input.

Interchangeability is contractual rather than capability equivalence: a fallback worker must satisfy the same role, scope, capability, tools, mutation ceiling, artifact contract, gate contract, and independence requirement.

## 2. Compatibility constraints

- Do not modify `shared/role-routing-policy.v1.json`, native role Tom's Obvious Minimal Language (TOML) files, the native role manifest, `agents-mode` defaults, or the frozen Version 1 parity baseline.
- Keep the Astra point route separately reviewable.
- Do not add General Language Model (GLM) providers to Version 1.
- Do not widen Kimi or Grok admission.
- Do not silently change provider, model, effort, runtime, role, scope, artifact, gate, tools, or mutation rights.
- Do not grant a worker acceptance, merge, release, publication, or Lead-transfer authority.
- Do not permit recursive delegation.

## 3. Architecture

The implementation deliberately separates the already reviewed selection core from the deep-review compatibility facade:

```text
Lead Host: Codex or Claude
        |
        v
resolve.py compatibility facade
  - strict input acquisition
  - request fingerprint
  - native-host boundary
  - explicit no-execution-authority result
        |
        v
_resolver_base.py reviewed V1 selection core
  - candidate validation
  - explicit priority and fallback
  - capability, mutation, tools, independence
        |
        v
selected candidate only
        |
        v
separately approved provider adapter
```

The facade preserves the accepted selection behavior instead of rewriting it during a security hardening pass. `_resolver_base.py` is internal implementation material, not an alternative public entrypoint. The supported public Python and CLI entrypoint remains `resolve.py`.

The resolver remains pure: it does not probe credentials, launch processes, mutate configuration, apply a patch, or authorize execution.

## 4. Request and decision contract

The public Python interface is:

```python
resolve_v1_worker_route(request: dict[str, object]) -> dict[str, object]
```

The exact request fields are:

```text
schemaVersion
dispatchId
policySnapshotId
leadHost
assignedRole
scopeId
capabilitySlot
mutationClass
requiredTools
excludedProviderFamilies
artifactContract
gateContract
candidates
```

Each candidate binds:

```text
candidateId
provider
runtime
providerFamily
model
effort
priority
availability
maxMutationClass
capabilities
tools
isolatedFromLead
maxDelegationDepth
authorizing
evidenceSnapshotId
```

A selected decision repeats the request contract and returns one normalized candidate. It also returns fallback and rejection evidence, request identity, and explicit authority boundaries.

## 5. Candidate admission

The Version 1 compatibility map is:

```text
codex  -> openai     -> codex-cli | codex-native
claude -> anthropic  -> claude-cli | claude-native
kimi   -> moonshot   -> kimi-cli
grok   -> xai        -> grok-cli
```

A `*-native` runtime is an in-host execution surface. It is legal only when the provider equals `leadHost`; cross-host native routing is rejected with `E_LEAD_WORKER_V1_NATIVE_RUNTIME_HOST_MISMATCH`. A same-provider CLI or native worker also requires `isolatedFromLead = true`.

The resolver rejects provider-family or runtime spoofing, excluded families, missing capabilities or tools, insufficient mutation admission, provider-ceiling claims, recursive delegation, and authorizing workers.

A candidate identifier is unique within a request. Multiple candidate configurations may intentionally refer to the same provider, model, and effort because they can represent different admission or availability observations; Version 1 does not add a global runtime-registry uniqueness rule. Version 2 owns that stronger registry invariant.

## 6. Fallback semantics

Candidates are evaluated by ascending `priority`, then `candidateId`.

Ordinary fallback states are:

```text
not-configured
not-entitled
quota-exhausted
temporary-transport-failure
unavailable
```

Provider hard failures are:

```text
auth-invalid
contract-violation
```

A hard failure does not authorize trusting any output from that candidate. A later explicit candidate may still be selected, but the decision remains marked for operator attention. Quality failure, unsafe output, budget exhaustion, and adapter containment failure are not invented as V1 availability states; they remain responsibilities of the adapter, Lead, or Version 2 policy.

## 7. Request identity and execution authority

For every structurally valid request, the resolver computes:

```text
requestFingerprintAlgorithm = sha256-canonical-json-v1
requestFingerprint = SHA-256(canonical JSON request)
```

Object-key order is normalized; array order remains significant. The fingerprint changes when the role, scope, artifact, gate, candidate set, availability evidence, or other request content changes. It lets adapters and ledger writers bind their records to the exact resolver input.

The digest is not a signature. It does not establish trust in caller-provided snapshots and does not prevent reuse unless the caller or ledger enforces dispatch uniqueness.

A selected decision always says:

```text
requiresAdapterAdmission = true
executionAuthorized = false
```

Thus `status = selected` means only that the candidate satisfies the resolver's compatibility contract. Executable identity, current credentials, containment, sandbox, tools, and provider admission must still be checked by the adapter.

## 8. Strict command-line input

The CLI reads a maximum of one mebibyte from standard input or one ordinary file. It rejects duplicate JSON keys, non-standard numeric constants, parser recursion, more than 32 nesting levels, and more than 8192 parsed nodes.

For a file request, the complete lexical absolute path is checked before and after reading. Symbolic links, reparse points, junctions, non-directory ancestors, and non-regular leaves fail closed. The opened descriptor must match the leaf identity observed before opening. Leaf size, modification time, and status-change time must remain stable.

Ancestor directories are bound by type, device, inode, mode, and reparse metadata—not by directory size or timestamps—so unrelated sibling file activity does not create spurious failures.

These checks reduce path substitution and time-of-check/time-of-use risk. They do not claim protection against a privileged attacker able to alter the process, kernel view, or trusted installer payload.

## 9. Review conclusions and non-goals

Deep review retained five proportionate changes:

1. canonical request fingerprint;
2. explicit separation of candidate selection from execution authorization;
3. rejection of foreign provider-native runtimes;
4. bounded, standards-compliant JSON structure;
5. stable no-follow path-chain acquisition without timestamp-sensitive ancestor false positives.

The review deliberately rejected a proposed ban on duplicate provider/model/effort tuples. Such a ban broke legitimate candidate variants and belongs in a trusted Version 2 runtime registry, not this caller-supplied Version 1 candidate list.

This patch does not add entitlement probing, signed evidence, dynamic rankings, a Lead lease, a scheduler, provider admission transitions, or automatic model debate. Those are Version 2 responsibilities.

## 10. Testing

The focused and deep-review suites cover:

- Codex/Claude Lead Host restriction;
- provider, runtime, family, and model separation;
- role/scope/artifact/gate preservation;
- explicit subscription and quota fallback;
- hard-failure visibility;
- review-family exclusion;
- mutation, tools, isolation, delegation, and authority;
- Kimi/Grok read-only ceilings and GLM exclusion;
- deterministic CLI output;
- duplicate-key, non-standard constant, deep-structure, oversized, linked-file, linked-ancestor, and file-replacement refusal;
- request fingerprint sensitivity;
- explicit `executionAuthorized = false`;
- absence of false rejection after unrelated ancestor-directory activity.

Full repository validators, installer projection checks, and publication gates remain required before leaving draft status.

## 11. Migration to Version 2

One Version 1 decision may map to one Version 2 portfolio slot only if role, scope, capability, tools, mutation, provider-family exclusions, artifact, gate, leaf-only delegation, and nonauthorizing authority are preserved. The Version 1 `requestFingerprint` may be recorded as migration provenance but is not a substitute for the Version 2 request, registry, policy, evaluation, and contract digests.

Version 2 replaces the fixed provider map with a dynamic registry and adds Lead lease fencing, portfolio routing, structured challenge, typed fallback, evidence freshness, and provider admission lifecycle.

## 12. Terms and abbreviations

- **CLI — Command-Line Interface:** command-line provider execution surface.
- **JSON — JavaScript Object Notation:** request and decision serialization format.
- **SHA-256 — Secure Hash Algorithm 256-bit:** digest algorithm used for request identity.
- **Lead Host:** Codex or Claude runtime holding the logical Lead role.
- **Native runtime:** worker execution surface inside the matching Lead Host runtime.
- **Fallback:** explicit selection of a later admitted candidate after a classified failure.
- **Admission:** verified permission for a runtime to perform a class of execution.
- **Time-of-check/time-of-use:** race between validation of a resource and its later use.

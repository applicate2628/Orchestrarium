---
name: lead-worker-routing
description: "Select one optional provider-neutral CLI worker under a Codex or Claude Lead with explicit fallback and unchanged Version 1 execution authority."
---

# Lead Worker Routing for Orchestrarium 1.x

## Purpose

Use this skill when the root conversation already holds the logical Lead in **Codex or Claude** and needs one bounded Command-Line Interface (CLI) worker. The worker may be Codex, Claude, Kimi, or Grok; any worker subscription may be absent, unpaid, quota-exhausted, or temporarily unavailable.

This is an additive Version 1 compatibility surface. It does not change native role files, the frozen Version 1 policy, provider credentials, provider admission, sandbox rules, review gates, or publication authority. General Language Model (GLM) providers and future providers belong to Version 2's dynamic registry.

## Lead and worker separation

- `leadHost` owns conversation state, decomposition, dispatch, synthesis, and the final response.
- A worker performs one `assignedRole`, one bounded `scopeId`, one `artifactContract`, and one `gateContract`.
- A worker has `maxDelegationDepth = 0` and `authorizing = false`.
- A same-provider worker must be an explicitly isolated invocation.
- A provider-native worker belongs only to the matching Lead Host. `claude-native` is not a Codex-hosted worker, and `codex-native` is not a Claude-hosted worker.
- The resolver never transfers the Lead role or lease.

## Invocation

1. Classify the role, bounded scope, capability, mutation class, exact required tools, artifact contract, gate contract, and any provider families excluded for independent review.
2. Bind the request to a unique `dispatchId` and current `policySnapshotId`.
3. Build an explicit candidate list from trusted caller-owned runtime evidence. Give every candidate an exact runtime, canonical provider family, runtime-observed model, effort, priority, availability, admission ceiling, capabilities, tools, and `evidenceSnapshotId`.
4. Invoke the only supported command-line entrypoint:

```text
python scripts/resolve.py --request-file <ordinary-request.json>
```

Use standard input for generated requests:

```text
producer | python scripts/resolve.py --request-file -
```

`_resolver_base.py` is a private import-only selection core. Direct execution always returns typed denial `E_LEAD_WORKER_V1_PRIVATE_ENTRYPOINT`; do not invoke or document it as an alternate CLI.

5. Recompute or compare `requestFingerprint` before forwarding the decision to an adapter or ledger writer.
6. Treat `status = selected` as candidate selection only. The returned decision always has:

```text
requiresAdapterAdmission = true
executionAuthorized = false
```

7. Launch only through the provider's separately approved adapter. The adapter must revalidate executable identity, admission, sandbox, tools, current availability, and the selected contract.
8. The Lead verifies the worker artifact, diff, logs, tests, and gate evidence before acceptance or forwarding.

The resolver does not launch a provider, inspect credentials, grant write access, validate the external evidence store, or record a successful review.

## Candidate order and fallback

Candidate `priority` is supplied by current operator or repository policy and referenced by `policySnapshotId`. Version 1 embeds no permanent vendor or model ranking. Ties are resolved by `candidateId`.

A candidate is selectable only when it:

- belongs to `codex | claude | kimi | grok`;
- has the canonical provider family and an admitted runtime identifier;
- is explicitly `available`;
- provides the requested capability and every required tool;
- is not in `excludedProviderFamilies`;
- satisfies the requested mutation class without exceeding the Version 1 provider ceiling;
- is isolated from a same-provider Lead;
- cannot delegate further;
- cannot authorize acceptance, merge, release, or publication.

`not-configured`, `not-entitled`, `quota-exhausted`, `temporary-transport-failure`, and `unavailable` are ordinary fallback states. `auth-invalid` and `contract-violation` are provider hard failures: a later explicit candidate may be selected, but the decision sets `hardFailureObserved = true` and `requiresOperatorAttention = true`. No output from the failed candidate is trusted.

Fallback changes only the worker realization. It cannot alter role, scope, capability, mutation, tools, provider-family exclusions, artifact, gate, or Lead ownership.

## Request identity and execution boundary

For a valid request, the resolver returns:

```text
requestFingerprintAlgorithm = sha256-canonical-json-v1
requestFingerprint = <64 lowercase hexadecimal characters>
```

The fingerprint is a Secure Hash Algorithm 256-bit digest of the exact request represented as canonical JSON with sorted object keys. Array order remains part of the request identity. This binds the decision to the submitted contract but is not a signature and does not prove that `policySnapshotId` or `evidenceSnapshotId` refers to trusted external data.

A malformed request has no fingerprint. A selected route is still nonauthorizing and cannot be used as proof that the adapter may execute it.

## Version 1 execution ceilings

- Codex and Claude candidates may declare up to `workspace-write`, subject to their real adapter and sandbox contracts.
- Kimi and Grok remain `read-only` in this resolver.
- Grok remains unlaunchable while its containment adapter reports unavailable.
- Kimi remains constrained by its current policy-bound wrapper.

Routing metadata cannot widen provider admission.

## Strict input handling

The public CLI accepts one UTF-8 JSON object from standard input or a stable ordinary file. It rejects:

- duplicate keys at any object depth;
- `NaN`, positive infinity, and negative infinity;
- JSON deeper than 32 levels or larger than 8192 parsed nodes;
- input over one mebibyte;
- symbolic links, Windows reparse points, junctions, non-regular leaves, and linked ancestors;
- replacement of the file or any path component during acquisition.

Directory snapshots bind identity and type only, so unrelated sibling creation does not produce a false rejection. The leaf additionally binds size, modification time, and status-change time.

## Result handling

A selected decision includes the exact request contract, normalized selected candidate, fallback events, policy rejections, fingerprint, and these invariant fields:

```text
requiresLeadVerification = true
requiresAdapterAdmission = true
executionAuthorized = false
maxDelegationDepth = 0
authorizing = false
```

A denied or unavailable result contains no selected worker. Never reinterpret a typed denial as permission to role-play or launch the provider.

## Terms and abbreviations

- **CLI — Command-Line Interface:** provider command-line runtime used for a worker invocation.
- **GLM — General Language Model:** model lineage reserved for Version 2 in this design.
- **Lead Host:** Codex or Claude runtime holding the logical Lead role and orchestration state.
- **Capability slot:** stable task ability requested from a worker, independent of model naming.
- **Fallback:** explicit selection of a later admitted candidate after a classified failure.
- **Admission:** verified permission for a provider runtime to perform a class of work or mutation.
- **Artifact contract:** identifier of the required worker output structure.
- **Gate contract:** identifier of verification required before the artifact may advance.
- **Request fingerprint:** canonical request digest used to detect contract substitution or replay mismatch.

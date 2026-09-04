---
name: lead-worker-routing
description: "Select one optional provider-neutral CLI worker under a Codex or Claude Lead with explicit availability fallback and unchanged Version 1 execution authority."
---

# Lead Worker Routing for Orchestrarium 1.x

## Purpose

Use this skill when the root conversation already holds the logical Lead in **Codex or Claude** and needs one bounded Command-Line Interface (CLI) worker. The worker may be Codex, Claude, Kimi, or Grok; any of those worker subscriptions may be absent, unpaid, quota-exhausted, or temporarily unavailable.

This skill is an additive Version 1 routing overlay. It does not change native role files, the frozen Version 1 policy, provider credentials, provider admission, sandbox rules, review gates, or publication authority. General Language Model (GLM) providers and other future providers belong to Version 2's dynamic registry and are not admitted here.

## Lead and worker are separate

- `leadHost` is the runtime that owns the conversation, work-item state, decomposition, dispatch, synthesis, and final response.
- A selected worker performs one `assignedRole`, one bounded `scopeId`, one `artifactContract`, and one `gateContract`.
- The worker has `maxDelegationDepth = 0` and `authorizing = false`.
- A worker using the same provider as the Lead must be an explicitly isolated invocation; the current Lead session is never reused as its own worker.
- The resolver never transfers the Lead role or lease.

## Invocation

1. Classify the needed role, bounded scope, capability, mutation class, exact required tools, artifact contract, gate contract, and any provider families excluded for independent review.
2. Bind the request to a unique `dispatchId` and the current `policySnapshotId`.
3. Build an explicit candidate list from currently configured runtime evidence. Give every candidate an exact runtime, canonical provider family, runtime-observed model, effort, priority, availability, admission ceiling, capabilities, tools, and `evidenceSnapshotId`.
4. Invoke the pure resolver:

```text
python scripts/resolve.py --request-file <ordinary-request.json>
```

Use standard input for generated or streamed requests:

```text
producer | python scripts/resolve.py --request-file -
```

Do not use symbolic links, named pipes, or process substitution as `--request-file`; they fail closed by design.

5. Treat the returned route as nonauthorizing. Launch it only through the provider's already approved execution adapter.
6. Verify the returned artifact, diff, logs, tests, and gate evidence in the Lead before acceptance or forwarding.

The resolver **does not launch** any provider, inspect credentials, mutate configuration, grant write access, apply a patch, validate the external evidence store, or record a successful review by itself.

## Candidate order and fallback

Candidate `priority` is supplied by the current operator or repository policy and bound by `policySnapshotId`. Version 1 does not embed one permanent ranking among vendors or model versions. Ties are resolved by `candidateId` so identical inputs produce identical decisions.

A candidate is selectable only when it:

- belongs to the Version 1 provider set `codex | claude | kimi | grok`;
- has the canonical provider family and an admitted runtime for that provider;
- is explicitly `available`;
- provides the requested capability and every required tool;
- is not in `excludedProviderFamilies`;
- satisfies the requested mutation class without exceeding provider admission;
- is isolated from a same-provider Lead;
- cannot delegate further;
- cannot authorize acceptance, merge, release, or publication.

`not-configured`, `not-entitled`, `quota-exhausted`, `temporary-transport-failure`, and `unavailable` are ordinary availability fallback states. `auth-invalid` and `contract-violation` are provider hard failures: a later explicit candidate may be selected, but the decision sets `hardFailureObserved = true` and `requiresOperatorAttention = true`. No output from a failed candidate is trusted.

Every fallback event preserves the candidate, provider, `evidenceSnapshotId`, availability, failure class, and stable error identifier. No ambient provider or model is substituted silently.

## Version 1 execution boundaries

Route metadata cannot widen a provider's execution rights. In this Version 1 overlay:

- Codex and Claude candidates may describe up to `workspace-write`, subject to their actual adapter and sandbox contract.
- Kimi and Grok remain `read-only` candidates in this resolver.
- Grok remains unlaunchable while its existing containment adapter reports unavailable.
- Kimi remains constrained by its existing policy-bound wrapper.

A represented candidate is not necessarily an executable candidate. The adapter remains the authority for actual provider admission, executable identity, and containment.

## Result handling

A selected decision binds and includes:

```text
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
selectedCandidate
fallbackApplied
fallbackEvents
rejections
selectionBasis
requiresLeadVerification = true
maxDelegationDepth = 0
authorizing = false
```

A denied or unavailable decision contains no selected worker. Do not reinterpret a typed denial as permission to role-play the requested provider.

## Terms and abbreviations

- **CLI — Command-Line Interface:** provider command-line runtime used for a worker invocation.
- **GLM — General Language Model:** model family reserved for Version 2 in this design.
- **Lead Host:** Codex or Claude runtime holding the logical Lead role and orchestration state.
- **Capability slot:** stable task ability requested from a worker, independent of model naming.
- **Fallback:** explicit selection of a later admitted candidate after an earlier candidate is unavailable.
- **Admission:** verified permission for a provider runtime to perform a class of work or mutation.
- **Provenance:** exact record of the provider, runtime, model, effort, evidence snapshot, and routing decision.

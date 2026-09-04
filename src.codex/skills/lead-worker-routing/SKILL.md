---
name: lead-worker-routing
description: "Select one optional provider-neutral CLI worker under a Codex or Claude Lead with explicit availability fallback and unchanged Version 1 execution authority."
---

# Lead Worker Routing for Orchestrarium 1.x

## Purpose

Use this skill when the root conversation already holds the logical Lead in **Codex or Claude** and needs one bounded CLI worker. The worker may be Codex, Claude, Kimi, or Grok; any of those worker subscriptions may be absent, unpaid, quota-exhausted, or temporarily unavailable.

This skill is an additive Version 1 routing overlay. It does not change native role files, the frozen Version 1 policy, provider credentials, provider admission, sandbox rules, review gates, or publication authority. GLM and other future providers belong to Version 2's dynamic registry and are not admitted here.

## Lead and worker are separate

- `leadHost` is the runtime that owns the conversation, work-item state, decomposition, dispatch, synthesis, and final response.
- A selected worker performs one role, one bounded scope, one artifact, and one gate.
- The worker has `maxDelegationDepth = 0` and `authorizing = false`.
- A worker using the same provider as the Lead must be an explicitly isolated invocation; the current Lead session is never reused as its own worker.
- The resolver never transfers the Lead role or lease.

## Invocation

1. Classify the needed capability, mutation class, and exact required tools before probing provider availability.
2. Build an explicit candidate list from currently configured runtime evidence. Give every candidate an exact runtime, provider family, runtime-observed model, effort, priority, availability, admission ceiling, capabilities, and tools.
3. Invoke the pure resolver:

```text
python scripts/resolve.py --request-file <request.json>
```

Use `--request-file -` to read the UTF-8 JSON request from standard input.

4. Treat the returned route as nonauthorizing. Launch it only through the provider's already approved execution adapter.
5. Verify the returned artifact, diff, logs, tests, and gate evidence in the Lead before acceptance or forwarding.

The resolver **does not launch** any provider, inspect credentials, mutate configuration, grant write access, apply a patch, or record a successful review by itself.

## Candidate order and fallback

Candidate `priority` is supplied by the current operator or repository policy. Version 1 does not embed one permanent ranking among vendors or model versions. Ties are resolved by `candidateId` so identical inputs produce identical decisions.

A candidate is selectable only when it:

- belongs to the Version 1 provider set `codex | claude | kimi | grok`;
- is explicitly `available`;
- provides the requested capability and every required tool;
- satisfies the requested mutation class without exceeding provider admission;
- is isolated from a same-provider Lead;
- cannot delegate further;
- cannot authorize acceptance, merge, release, or publication.

`not-configured`, `not-entitled`, `quota-exhausted`, `temporary-transport-failure`, `auth-invalid`, `contract-violation`, and `unavailable` are recorded as exact fallback events. A later candidate may be selected, but no ambient provider or model is substituted silently.

## Version 1 execution boundaries

The route metadata cannot widen a provider's execution rights. In this Version 1 overlay:

- Codex and Claude candidates may describe up to `workspace-write`, subject to their actual adapter and sandbox contract.
- Kimi and Grok remain `read-only` candidates in this resolver.
- Grok remains unlaunchable while its existing containment adapter reports unavailable.
- Kimi remains constrained by its existing policy-bound wrapper.

A represented candidate is not necessarily an executable candidate. The adapter remains the authority for actual provider admission and containment.

## Result handling

A selected decision includes:

```text
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
- **Lead Host:** Codex or Claude runtime holding the logical Lead role and orchestration state.
- **Capability slot:** stable task ability requested from a worker, independent of model naming.
- **Fallback:** explicit selection of a later admitted candidate after an earlier candidate is unavailable.
- **Admission:** verified permission for a provider runtime to perform a class of work or mutation.
- **Provenance:** exact record of the provider, runtime, model, effort, and routing decision.

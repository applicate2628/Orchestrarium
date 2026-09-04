---
name: lead-worker-pool
description: "Route an eligible CLI worker from a Codex- or Claude-hosted Lead, including explicit cross-provider fallback when a preferred subscription, quota, or runtime is unavailable."
---

# Lead Worker Pool for Orchestrarium 1.x

## Purpose

Use this skill when the main conversation holds Lead in Codex or Claude and an eligible worker, consultant, or reviewer lane should run through a command-line provider. The logical Lead remains in the main conversation; this skill selects one leaf worker route and never transfers orchestration ownership.

Version 1 admits only the existing provider set: Codex, Claude, Kimi, and Grok. GLM is Version 2 only.

## Stable invariants

- Lead is a logical role hosted by Codex or Claude, not a model name.
- A selected worker is a leaf: `maxDelegationDepth = 0`.
- The worker keeps the assigned role, scope, mutation class, artifact contract, and gate contract when the provider changes.
- Every worker result is nonauthorizing and requires Lead verification.
- Provider substitution is explicit in the returned fallback trace; there is no hidden fallback.
- A provider being unconfigured, unpaid, out of quota, or temporarily unavailable is a normal routing condition, not a failure of the whole work item.
- Capability, tool access, mutation admission, and reviewer independence are hard gates.
- A same-host CLI rerun is excluded by default and requires explicit admission.
- Provider-family diversity is distinct from model diversity. Two models from one vendor do not satisfy an independent-family review requirement.

## Routing input

The candidate order is supplied by the caller from the active policy and current evidence snapshot. The resolver does not encode a permanent vendor ranking or a permanent model-to-role assignment.

Each candidate carries exactly:

```text
routeId
provider
runtime
model
effort
providerFamily
status
admission
capabilities
tools
```

`model` and `effort` are observed runtime identities. They are recorded for provenance but are not compared through one universal quality ladder.

Availability states are:

```text
available
not-configured
not-entitled
quota-exhausted
temporary-failure
auth-invalid
quarantined
unavailable
unknown
```

`auth-invalid`, `quarantined`, and `unknown` additionally set `operatorActionRequired = true`. The Lead may still choose another admissible provider, but the condition remains visible.

## Selection procedure

1. Confirm that the assigned role is eligible for the existing external-worker, external-reviewer, or consultant adapter.
2. Preserve the accepted role, scope, artifact, and gate contracts.
3. Build an ordered candidate list from the current policy, runtime inventory, entitlement state, and task-specific evidence.
4. Run `scripts/resolve.py --request <json-file>`.
5. Launch only the returned provider through its already approved wrapper.
6. Record requested provider, resolved provider, observed model, effort, fallback trace, and artifact identity in normal execution provenance.
7. Verify the artifact, diff, logs, tests, or review findings in the Lead lane before acceptance.

An explicit provider request may either prohibit substitution or allow cross-provider fallback. When substitution is prohibited, an unavailable requested provider returns a typed non-success result instead of silently selecting another vendor.

## Independence and disagreement

For an independent reviewer, provide `requireIndependentFamily = true` and the author's `authorProviderFamily`. Same-family candidates are rejected for that route even when their model names differ.

Multiple providers may be used to expand scope, generate independent proposals, or challenge an accepted direction. They still exchange artifacts through Lead rather than assigning work directly to each other. Empirical tests, proofs, benchmarks, and repository evidence arbitrate disagreements; model voting does not.

## Version 1 boundaries

- This skill is an additive compatibility overlay. It does not rewrite native role TOML, the pinned Version 1 role-routing policy, operator presets, provider credentials, or wrapper admission.
- It does not make an unavailable wrapper executable. Current provider admission remains authoritative; for example, a read-only provider cannot become a bounded-write worker through this resolver.
- It does not automate Lead-host failover. Codex and Claude can each host Lead, while cross-host continuation still uses durable work-item state. Automatic lease transfer is a Version 2 concern.
- It does not add GLM or future providers to Version 1.
- It does not authorize merge, release, publication, or acceptance.

## Terms and Abbreviations

- **CLI — Command-Line Interface:** a provider's non-interactive command-line execution surface.
- **Lead:** the main-conversation owner of routing, integration, evidence verification, and task-memory state.
- **Leaf worker:** a scoped subagent that cannot delegate further.
- **Fallback trace:** the ordered record of rejected candidates and the reason each was skipped.
- **Admission:** the maximum permitted mutation and tool surface for one provider route.
- **Provider family:** the vendor lineage used when evaluating independence.
- **TOML — Tom's Obvious Minimal Language:** the native Codex role configuration format.

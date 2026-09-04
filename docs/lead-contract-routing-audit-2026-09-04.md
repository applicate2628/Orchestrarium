# Provider-Neutral Lead and Worker Routing Audit

## Contents

1. [Audited state](#1-audited-state)
2. [Established repository constraints](#2-established-repository-constraints)
3. [Defects in the previous routing model](#3-defects-in-the-previous-routing-model)
4. [Version 1 decision](#4-version-1-decision)
5. [Full-review findings and corrections](#5-full-review-findings-and-corrections)
6. [Fallback and subscription semantics](#6-fallback-and-subscription-semantics)
7. [Provider admission boundary](#7-provider-admission-boundary)
8. [Version 2 direction](#8-version-2-direction)
9. [Verification obligations](#9-verification-obligations)
10. [Terms and abbreviations](#10-terms-and-abbreviations)

## 1. Audited state

The review covers the Version 1 baseline on `main`, the open lifecycle hotfix branch, the policy-overlay work, the Astra routing Pull Request, the shared subagent operating model, native Codex role bindings, provider prompt transports, agents-mode schemas, and the current Kimi and Grok admission paths.

The Astra route remains a narrow point upgrade. The provider-neutral Lead/worker route is stacked on it so that the new behavior can be reviewed without rewriting the frozen Version 1 policy or folding Version 2 architecture into a compatibility patch.

## 2. Established repository constraints

Version 1 model and provider semantics are distributed across native role Tom's Obvious Minimal Language (TOML) files, a hash-bound role manifest, `role-routing-policy.v1.json`, agents-mode schema/default/preset files, provider prompt transport, installer ownership, skills, references, and tests. Rewriting native model bindings would require a broad exact-prior installer migration.

The shared operating model already establishes that the root conversation holding Lead is the only dispatcher and work-item lifecycle owner. A worker returns one artifact and evidence, cannot become Lead, cannot launch another wrapper, and cannot treat its own `PASS` claim as accepted proof.

## 3. Defects in the previous routing model

The previous discussion and implementation surfaces mixed four independent concepts:

1. the runtime hosting the logical Lead;
2. the runtime launching a worker;
3. the provider family used to assess evidence independence;
4. the exact runtime-observed model and effort.

It also treated provider availability as a binary implementation failure. That is unsuitable when Codex, Claude, Kimi, and Grok subscriptions may independently be absent or quota-exhausted.

Finally, one permanent provider order cannot serve every capability slot. Interchangeability means a common contract and honest fallback; it does not mean equal task competence or identical tool and mutation support.

## 4. Version 1 decision

Version 1 adds the provider-neutral `lead-worker-routing` skill and a pure resolver. The logical Lead may be hosted only by Codex or Claude. Eligible worker identifiers are Codex, Claude, Kimi, and Grok; General Language Model (GLM) providers are intentionally reserved for Version 2.

The resolver accepts an exact candidate list whose ordering is supplied by current operator or repository policy. It validates capability, mutation class, tools, provider/runtime identity, review independence, same-host isolation, leaf-only delegation, nonauthorizing authority, and explicit availability. It returns one exact worker route or a typed non-success decision and does not launch a process.

The change does not modify native roles, the role manifest, `role-routing-policy.v1.json`, agents-mode defaults, the frozen parity baseline, or provider credentials.

## 5. Full-review findings and corrections

The first implementation selected a capability but did not bind the assigned role, bounded scope, artifact contract, gate contract, dispatch identity, or policy snapshot. A fallback worker therefore had no machine-readable obligation to return the same artifact under the same acceptance gate. The corrected request and decision include:

```text
dispatchId
policySnapshotId
assignedRole
scopeId
artifactContract
gateContract
```

The first implementation also trusted caller-declared runtime identity after checking only provider family. The corrected resolver admits only the Version 1 runtime identifiers declared for each provider.

Independent review was described in prose but could not be enforced. The corrected request adds `excludedProviderFamilies`, allowing a reviewer route to reject the author's provider family.

Candidate availability and model observations were not tied to evidence provenance. Every candidate now requires `evidenceSnapshotId`, which is preserved in selected routes and fallback events.

The first command-line reader used ordinary `json.loads()` and `Path.open()`. It therefore accepted duplicate object keys and followed symbolic links. The corrected reader:

- rejects duplicate keys at any object depth;
- accepts only a stable ordinary request file or standard input;
- rejects symbolic links, reparse points, non-regular files, replacement during reading, and inputs larger than 1 mebibyte;
- emits separate stable identifiers for duplicate-key, unsafe-file, oversized, and malformed requests.

## 6. Fallback and subscription semantics

The following are normal availability fallback states:

- `not-configured`;
- `not-entitled`;
- `quota-exhausted`;
- `temporary-transport-failure`;
- `unavailable`.

`auth-invalid` and `contract-violation` are provider hard failures. A later explicit candidate may still be selected because no result from the failed provider is trusted, but the decision records `hardFailureObserved = true` and `requiresOperatorAttention = true`.

Fallback never changes the requested role, scope, capability, mutation class, tool set, provider-family exclusion, artifact contract, gate contract, or Lead ownership. It changes only the selected worker realization. There is no ambient or silent fallback.

## 7. Provider admission boundary

The resolver represents routing candidates but does not grant execution authority. Existing adapters remain authoritative.

- Codex and Claude can be candidates for read or write work only within their actual sandbox and wrapper contracts.
- Kimi remains constrained by its policy-bound Version 1 read-only path.
- Grok remains unavailable while its containment path returns a typed refusal.
- Kimi or Grok metadata claiming write access is rejected by the resolver.

This distinction prevents routing configuration from bypassing provider containment.

## 8. Version 2 direction

Version 2 replaces the fixed provider set with a dynamic model registry and separates:

```text
logical Lead contract
Lead Host adapter
worker runtime
provider family
model identity and effort
provider admission
availability and entitlement
evidence freshness
```

It selects a portfolio of roles such as primary, scope-expander, challenger, implementer, reviewer, and visual validator. Hard admission and quality gates run before scope coverage, independent challenge, evidence quality, accepted-result cost, and latency ranking. Exact model generation numbers live only in runtime registry snapshots, not in stable role policy. GLM enters only through this Version 2 registry.

## 9. Verification obligations

Before publication, the implementation must pass focused resolver tests, Python compilation, repository skill-pack validators, installer projection checks, and publication-safety checks in a full checkout. The branch must remain stacked on the exact reviewed Astra routing head until its base changes are merged or rebased deliberately.

## 10. Terms and abbreviations

- **CLI — Command-Line Interface:** command-line provider runtime.
- **GLM — General Language Model:** future external model lineage reserved for Version 2.
- **Lead Host:** Codex or Claude environment hosting the logical Lead.
- **TOML — Tom's Obvious Minimal Language:** native role configuration format.
- **Fallback:** explicit selection of a later admitted candidate after a typed failure.
- **Admission:** verified provider permission for a class of execution.
- **Capability slot:** stable required ability independent of a specific model version.
- **Provider family:** vendor/model family used when assessing evidence independence.

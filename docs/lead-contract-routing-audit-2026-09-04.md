# Provider-Neutral Lead and Worker Routing Audit

## Contents

1. [Audited state](#1-audited-state)
2. [Established repository constraints](#2-established-repository-constraints)
3. [Defects in the previous routing model](#3-defects-in-the-previous-routing-model)
4. [Version 1 decision](#4-version-1-decision)
5. [Fallback and subscription semantics](#5-fallback-and-subscription-semantics)
6. [Provider admission boundary](#6-provider-admission-boundary)
7. [Version 2 direction](#7-version-2-direction)
8. [Verification obligations](#8-verification-obligations)
9. [Terms and abbreviations](#9-terms-and-abbreviations)

## 1. Audited state

The review covers the Version 1 baseline on `main`, the open lifecycle hotfix branch, the policy-overlay work, the Astra routing Pull Request, the shared subagent operating model, native Codex role bindings, provider prompt transports, agents-mode schemas, and the current Kimi and Grok admission paths.

The Astra route remains a narrow point upgrade. The provider-neutral Lead/worker route is stacked on it so that the new behavior can be reviewed without rewriting the frozen Version 1 policy or folding Version 2 architecture into a compatibility patch.

## 2. Established repository constraints

Version 1 model and provider semantics are distributed across native role TOML, a hash-bound role manifest, `role-routing-policy.v1.json`, agents-mode schema/default/preset files, provider prompt transport, installer ownership, skills, references, and tests. Rewriting the native model bindings would require a broad exact-prior installer migration.

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

Version 1 adds the provider-neutral `lead-worker-routing` skill and a pure resolver. The logical Lead may be hosted only by Codex or Claude. Eligible worker identifiers are Codex, Claude, Kimi, and Grok; GLM is intentionally reserved for Version 2.

The resolver accepts an exact candidate list whose ordering is supplied by current operator or repository policy. It validates capability, mutation class, tools, same-host isolation, leaf-only delegation, nonauthorizing authority, and explicit availability. It returns one exact worker route or a typed non-success decision and does not launch a process.

The change does not modify native roles, the role manifest, `role-routing-policy.v1.json`, agents-mode defaults, the frozen parity baseline, or provider credentials.

## 5. Fallback and subscription semantics

The following are normal candidate states:

- `not-configured`;
- `not-entitled`;
- `quota-exhausted`;
- `temporary-transport-failure`;
- `unavailable`.

They are recorded as fallback events, after which a later explicit candidate may be selected. `auth-invalid` and `contract-violation` are also recorded, but no output from the failed candidate is trusted.

Fallback never changes the requested capability, mutation class, tool set, artifact contract, gate, or Lead ownership. It changes only the selected worker realization. There is no ambient or silent fallback.

## 6. Provider admission boundary

The resolver represents routing candidates but does not grant execution authority. Existing adapters remain authoritative.

- Codex and Claude can be candidates for read or write work only within their actual sandbox and wrapper contracts.
- Kimi remains constrained by its policy-bound Version 1 read-only path.
- Grok remains unavailable while its containment path returns a typed refusal.
- Kimi or Grok metadata claiming write access is rejected by the resolver.

This distinction prevents routing configuration from bypassing provider containment.

## 7. Version 2 direction

Version 2 replaces the fixed provider set with a dynamic model registry and separates:

```text
logical Lead contract
Lead Host adapter
worker runtime
provider family
model identity
model effort
provider admission
availability and entitlement
```

It selects a portfolio of roles such as primary, scope-expander, challenger, implementer, reviewer, and visual validator. Hard admission and quality gates run before scope coverage, independent challenge, evidence quality, accepted-result cost, and latency ranking. Exact model generation numbers live only in runtime registry snapshots, not in stable role policy.

## 8. Verification obligations

Before publication, the implementation must pass focused resolver tests, Python compilation, repository skill-pack validators, installer projection checks, and publication safety checks in a full checkout. The branch must remain stacked on the exact reviewed Astra routing head until its base changes are merged or rebased deliberately.

## 9. Terms and abbreviations

- **CLI — Command-Line Interface:** command-line provider runtime.
- **Lead Host:** Codex or Claude environment hosting the logical Lead.
- **TOML — Tom's Obvious Minimal Language:** native role configuration format.
- **Fallback:** explicit selection of a later admitted candidate after a typed failure.
- **Admission:** verified provider permission for a class of execution.
- **Capability slot:** stable required ability independent of a specific model version.
- **Provider family:** vendor/model family used when assessing evidence independence.

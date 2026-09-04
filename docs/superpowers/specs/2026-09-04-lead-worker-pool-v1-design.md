# Lead Worker Pool Version 1 Design

## Contents

1. [Goal](#1-goal)
2. [Repository constraints](#2-repository-constraints)
3. [Architecture](#3-architecture)
4. [Resolver contract](#4-resolver-contract)
5. [Fallback semantics](#5-fallback-semantics)
6. [Independence and model diversity](#6-independence-and-model-diversity)
7. [Compatibility and migration](#7-compatibility-and-migration)
8. [Verification](#8-verification)
9. [Non-goals](#9-non-goals)
10. [Terms and abbreviations](#10-terms-and-abbreviations)

## 1. Goal

Add a provider-neutral Version 1 compatibility overlay that lets the main Lead run in either Codex or Claude and select an eligible command-line worker from Codex, Claude, Kimi, or Grok. A provider that is unconfigured, unpaid, out of quota, or temporarily unavailable is skipped through an explicit, recorded fallback rather than breaking the whole work item.

The change must preserve the accepted role, scope, mutation class, artifact contract, and gate contract when the selected provider changes.

## 2. Repository constraints

The existing shared operating model already requires the root main conversation to hold Lead, forbids recursive provider dispatch, and treats leaf `PASS` as a claim rather than proof. Codex and Claude each implement Lead as a main-session role. Existing external adapters cover worker, reviewer, and consultant lanes but not owner roles.

Version 1 has broad hash-pinned ownership around native role TOML, the role manifest, provider transports, defaults, presets, and the role-routing policy. This change therefore must be additive:

- no native role TOML rewrite;
- no change to `shared/role-routing-policy.v1.json`;
- no change to existing `agents-mode` defaults or presets;
- no change to provider credentials or executable admission;
- no implicit promotion of a read-only provider to bounded write;
- no new Version 1 provider beyond Codex, Claude, Kimi, and Grok.

The existing explicit Astra route remains separate. It chooses one exact Codex-family model profile for an already admitted task; the new worker-pool resolver chooses a provider route for an already admitted external worker, reviewer, or consultant lane.

## 3. Architecture

```text
Logical Lead in the main conversation
        │
        ├── Codex-hosted Lead
        └── Claude-hosted Lead
                    │
                    ▼
          Lead Worker Pool resolver
                    │
       caller-ranked candidate snapshot
                    │
                    ▼
       Codex | Claude | Kimi | Grok CLI
                    │
                    ▼
     one leaf artifact + one gate claim
                    │
                    ▼
             Lead verification
```

The Lead host and worker provider are distinct facts. The active Lead may call the other Lead-capable runtime as a normal leaf worker. A same-host command-line rerun is excluded by default because it is not an external opinion; it can be admitted explicitly for isolation, a different model profile, or a deliberate independent rerun.

The resolver is pure. It validates and selects a route but does not probe the network, launch a provider, edit configuration, or accept an artifact.

## 4. Resolver contract

### 4.1 Request

The resolver consumes:

- `leadHost`: `codex | claude`;
- `assignedRole`: the already admitted internal role;
- `capabilitySlot`: task-specific capability required from the worker;
- `mutationClass`: `read-only | bounded-write`;
- `artifactContract`: exact expected artifact identity;
- `gateContract`: exact acceptance or review gate identity;
- `requiredTools`: exact stable tool classes;
- `requestedProvider`: optional explicit provider preference;
- `allowProviderFallback`: whether an explicit provider may be substituted;
- `allowSelfProvider`: whether the Lead host may launch its own CLI as a leaf;
- `requireIndependentFamily`: whether reviewer family must differ from the author;
- `authorProviderFamily`: author family when independence is required;
- `candidates`: caller-ranked current route snapshot.

Each candidate contains exactly:

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

Exact model identifiers are runtime observations, not stable policy keys. Candidate order comes from the caller's active policy and evidence snapshot; the resolver has no permanent vendor rank.

### 4.2 Hard gates

For each candidate, in order:

1. same-host admission;
2. runtime and entitlement status;
3. required capability;
4. mutation admission;
5. required tools;
6. provider-family independence when required.

A rejected candidate produces one typed row in `fallbackTrace`.

### 4.3 Decision

A selected decision returns:

- requested and resolved provider;
- observed runtime, model, effort, and provider family;
- complete ordered candidate identities;
- complete fallback trace;
- whether operator action is also required;
- the unchanged role, capability, mutation, artifact, and gate contracts;
- `maxDelegationDepth = 0`;
- `requiresLeadVerification = true`;
- `authorizing = false`.

No admissible route returns typed `unavailable`; malformed requests return typed `denied`.

## 5. Fallback semantics

Availability states are:

| State | Meaning | May another provider be selected? | Operator action flag |
|---|---|---:|---:|
| `available` | route can be considered | yes | no |
| `not-configured` | no local setup | yes | no |
| `not-entitled` | subscription or entitlement absent | yes | no |
| `quota-exhausted` | current provider quota exhausted | yes | no |
| `temporary-failure` | transient transport or vendor failure | yes | no |
| `auth-invalid` | configured authentication is invalid | yes, with trace | yes |
| `quarantined` | route was removed from use by policy or evidence | yes, with trace | yes |
| `unavailable` | route is unavailable for another known reason | yes | no |
| `unknown` | availability is not established | yes, with trace | yes |

Fallback means provider substitution under the same task contract. It does not mean weakening role eligibility, mutation rights, tools, independence, or evidence gates.

An explicit provider request with `allowProviderFallback = false` never substitutes another vendor. An explicit request with fallback enabled tries requested-provider candidates first and then the remaining caller-ranked routes. A missing requested provider is recorded separately from an observed unavailable provider.

## 6. Independence and model diversity

Provider interchangeability does not imply equivalent capabilities. The caller ranks candidates for the current capability slot using current evidence. The resolver only enforces hard gates and preserves the order.

Model diversity has two uses:

1. resilience when a paid provider is absent or exhausted;
2. broader solution search through independent proposals, scope expansion, and challenge.

Version 1 supports the second use through multiple separate leaf dispatches controlled by Lead. It does not implement autonomous peer debate. Artifacts return to Lead, which may dispatch a different provider to critique them. Tests, proofs, benchmarks, diffs, and logs arbitrate disagreements.

Different models from one provider family may be useful but do not satisfy an independent-family review requirement.

## 7. Compatibility and migration

The overlay is installed as a new `lead-worker-pool` skill with a skill-local pure resolver. It does not replace:

- `externalProvider` or current priority profiles;
- existing provider wrappers;
- the Astra-specific route;
- internal native role routing;
- the external role taxonomy.

The Lead builds the candidate snapshot from the currently effective Version 1 policy and actual runtime state, calls the resolver, then invokes only the selected already-approved wrapper.

GLM is intentionally absent from Version 1. Its provider adapter and dynamic registration belong to Version 2.

Automatic Lead-host transfer is also deferred. A user may start or resume the logical Lead in Codex or Claude using durable `work-items/` state, but Version 1 does not implement a lease or automatic host takeover.

## 8. Verification

Required focused tests cover:

- Codex and Claude as valid Lead hosts;
- cross-provider fallback after absent entitlement or quota;
- caller-controlled candidate order;
- same-host exclusion and explicit admission;
- provider-family-independent review;
- capability, tool, and mutation hard gates;
- every availability state and operator-action flag;
- explicit no-fallback behavior;
- missing requested provider behavior;
- no admissible route;
- strict request shape and duplicate route rejection;
- deterministic command-line JSON output;
- rejection of GLM in Version 1;
- skill metadata and absence of version-pinned model policy.

Full-checkout integration still requires provider-pack validation, installer checks, Python compilation, `git diff --check`, and the repository publication gate before merge.

## 9. Non-goals

- redesigning Version 1 model tiers;
- choosing a permanent best provider for any capability;
- adding GLM to Version 1;
- making Grok or Kimi write-capable without their own admission evidence;
- automatic Lead lease transfer;
- accepting, merging, releasing, or publishing worker output.

## 10. Terms and abbreviations

- **CLI — Command-Line Interface:** non-interactive provider execution surface.
- **Lead Host:** Codex or Claude main conversation currently holding the logical Lead role.
- **Capability slot:** stable task ability required from a worker, independent of model name.
- **Admission:** maximum allowed mutation and tool surface for one route.
- **Fallback trace:** ordered record explaining why earlier candidates were skipped.
- **Provider family:** vendor lineage used to judge independence.
- **TOML — Tom's Obvious Minimal Language:** native Codex role configuration format.

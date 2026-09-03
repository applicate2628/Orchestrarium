---
name: policy-overlay
description: Resolve optional non-authorizing behavior policies for an exact Orchestrarium provider, lane, and agent target; use for lean implementation, complexity-only review, external prompt composition, policy propagation, or Ponytail coexistence checks.
---

# Policy Overlay

Use this common skill to add an optional behavior policy after Orchestrarium has already selected the role, provider, lane, and authorization boundary. A policy overlay changes *how* admitted work is approached; it never authorizes work, changes the role owner, or weakens mandatory governance.

## Table of contents

- [Authority boundary](#authority-boundary)
- [Selection and restriction](#selection-and-restriction)
- [Resolve one exact projection](#resolve-one-exact-projection)
- [Prompt composition](#prompt-composition)
- [Built-in overlays](#built-in-overlays)
- [Ponytail coexistence](#ponytail-coexistence)
- [Orchestrarium 1.x boundary](#orchestrarium-1x-boundary)
- [Terms and abbreviations](#terms-and-abbreviations)

## Authority boundary

The deterministic precedence is:

1. hard governance and safety;
2. explicit user requirements;
3. assigned role contract;
4. governing project policy;
5. optional policy overlays;
6. task body.

An overlay is always non-authorizing. It cannot remove or weaken security, trust-boundary validation, data-loss protection, recovery, accessibility, mandatory verification, publication gates, role authorization, project constraints, or explicit user requirements.

No configured selection means no overlay and preserves existing Orchestrarium behavior.

## Selection and restriction

The user-owned selection file is optional:

```yaml
# ~/.orche/config.yaml
policyOverlays: [lean-implementation]
```

A project may restrict that selection but may not enable an overlay by itself:

```yaml
# <project>/.orche/policy.yaml
allowedPolicyOverlays: [lean-implementation, complexity-review]
deniedPolicyOverlays: []
```

Only these top-level inline-list keys are interpreted. Machine state, caches, package presence, repository prose, and an installed third-party package never select a policy.

An explicit caller selection is still subject to the project allowlist and denylist.

## Resolve one exact projection

The helper is located at `scripts/policy-overlays.py` inside this skill. Resolve the exact tuple rather than copying every selected overlay into every agent:

```bash
python scripts/policy-overlays.py \
  --provider codex \
  --project-root /path/to/project \
  --home /path/to/home \
  --lane worker.default-implementation \
  --target external-worker \
  --format instructions
```

Supported targets are:

- `main-agent`;
- `internal-subagent`;
- `external-worker`;
- `external-reviewer`;
- `consultant`.

The catalog under `policy-overlays.v1.json` owns provider, lane, target, propagation, ordering, and conflict rules. Empty output means the selected overlay is not applicable to that exact tuple.

Invalid identifiers, unknown overlays, conflicts, unsafe catalog paths, linked instruction files, malformed configuration, or a project restriction return `E_POLICY_OVERLAY_INVALID` and exit status `2`.

## Prompt composition

For an internal agent, the invoking Lead or adapter may append only the non-empty rendered frame to the already assigned role prompt. Version 1.x does not inject the frame automatically.

For an external worker or reviewer, the invoking Lead or adapter composes the file-based prompt in this order:

```text
external governance capsule
assigned role contract
ORCHESTRARIUM_OPTIONAL_POLICY_OVERLAYS_V1 frame bound to provider/lane/target
task body
```

Never send all active overlays blindly. Resolve the external provider, lane, and target first. An overlay filtered out for that tuple is absent from the prompt.

## Built-in overlays

### Lean implementation

`lean-implementation` applies only to admitted implementation lanes and to main agents, internal subagents, or external workers. It asks the implementer to understand the owner first, then prefer reuse, the language standard library, native platform features, admitted dependencies, and the smallest coherent owner-level fix. It never reduces required verification or safety controls.

### Complexity review

`complexity-review` is an additional non-authorizing opinion for selected review lanes. It looks only for avoidable dependencies, duplicated standard-library or native behavior, one-implementation abstractions, one-product factories, delegating wrappers, speculative configuration, dead compatibility paths, and removable boilerplate.

It does not replace correctness, security, performance, accessibility, recovery, or publication review. Findings from this overlay are advisory until the owning reviewer accepts them.

## Ponytail coexistence

[Ponytail](https://github.com/DietrichGebert/ponytail) remains an independent host-managed package. Orchestrarium does not vendor it, execute its JavaScript runtime, install it automatically, read or write its mode configuration, or claim ownership of its hooks and skills.

The supported coexistence contract is:

- Orchestrarium installation and reinstallation preserve unrelated third-party skills, settings, and hook entries;
- Ponytail `SessionStart`, `SubagentStart`, and `UserPromptSubmit` entries may coexist with Orchestrarium hooks;
- Orchestrarium removes or replaces only artifacts proven to be Orchestrarium-owned stock;
- Ponytail owns its `off`, `lite`, `full`, `ultra`, and review behavior;
- Orchestrarium owns role routing, authorization, project governance, and overlay projection;
- installing Ponytail never implicitly selects an Orchestrarium overlay;
- installing Orchestrarium never implicitly enables Ponytail.

The two Orche-native built-in overlays are independently authored. They borrow the general ideas of reuse-first implementation and complexity-only review, not Ponytail source code or runtime behavior.

## Orchestrarium 1.x boundary

Version 1.x provides a declarative catalog, bounded local configuration, deterministic resolution, provider/lane/target filtering, non-authorizing prompt rendering, explicit activation, and compatibility regression tests.

Version 1.x does not provide a remote policy registry, marketplace, dependency solver, executable third-party overlay hooks, dynamic code loading from external packages, hot reload, or a sandbox for arbitrary overlay programs. Those are separate Orchestrarium 2.x design questions.

## Terms and abbreviations

- **API — Application Programming Interface:** a stable callable or command-line contract used by another component.
- **Behavior policy:** optional guidance that changes the implementation or review approach without changing authorization.
- **Lane:** the typed Orchestrarium work category, such as `worker.default-implementation` or `review.pre-pr`.
- **Overlay:** an additional instruction layer composed after governance and the role contract.
- **Ponytail:** an independent MIT-licensed external package that promotes minimal, reuse-first coding behavior.
- **Provider:** the execution environment selected for a lane, such as Codex, Claude, or explicit read-only Kimi review.
- **SessionStart:** a host lifecycle event emitted at session start or restoration.
- **Subagent:** a child agent assigned a narrower role or task by the main agent.
- **YAGNI — You Aren't Gonna Need It:** the principle of not implementing speculative functionality before a demonstrated need.

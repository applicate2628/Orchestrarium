# Optional policy overlays and Ponytail coexistence

## Table of contents

- [Decision](#decision)
- [Why an overlay is not a role](#why-an-overlay-is-not-a-role)
- [Configuration and precedence](#configuration-and-precedence)
- [Propagation](#propagation)
- [Built-in Orchestrarium policies](#built-in-orchestrarium-policies)
- [Ponytail compatibility](#ponytail-compatibility)
- [Installation and operation](#installation-and-operation)
- [Version 1.x and Version 2.x boundary](#version-1x-and-version-2x-boundary)
- [Recovery](#recovery)
- [Terms and abbreviations](#terms-and-abbreviations)

## Decision

Orchestrarium Version 1.x gains a provider-neutral instruction-overlay seam and two optional built-in policies. Ponytail remains an independent package. The implementation deliberately chooses compatibility and a generic API instead of embedding Ponytail or adding Node.js as an Orchestrarium dependency.

The feature is dormant by default. Existing users without `~/.orche/config.yaml` receive the same role selection, prompts, hooks, and validation behavior as before.

## Why an overlay is not a role

A role owns a task boundary, decisions, artifacts, and closure evidence. An overlay owns none of those. It is a filtered instruction fragment applied only after the role and lane are known.

A skill can contain executable workflow and references. The `policy-overlay` skill owns the resolver, but each resolved overlay is only a non-authorizing instruction layer.

`agents-mode` controls routing posture and provider preferences. Policy-overlay configuration controls optional implementation/review behavior and therefore uses a separate narrow configuration surface. The project-side file may restrict a user selection but cannot enable one, preventing a cloned repository from silently activating an optional behavior mode.

## Configuration and precedence

User selection:

```yaml
# ~/.orche/config.yaml
policyOverlays: [lean-implementation, complexity-review]
```

Optional project restriction:

```yaml
# <project>/.orche/policy.yaml
allowedPolicyOverlays: [lean-implementation, complexity-review]
deniedPolicyOverlays: []
```

The resolver accepts only the documented top-level inline lists. It rejects unknown identifiers, duplicates, allow/deny overlap, linked configuration files, unsafe catalog paths, and conflicting overlays.

Configuration files use UTF-8 (Unicode Transformation Format, 8-bit), with or without one leading byte-order mark. Spaces or tabs before the key delimiter `:` are accepted; duplicate owned keys and non-list values still fail rather than being silently ignored.

Top-level owned keys must be bare identifiers. A quoted `policyOverlays`, `allowedPolicyOverlays`, or `deniedPolicyOverlays` is rejected as unsupported, rather than silently treated as absent. Unrelated and indented nested settings remain outside this selector and are ignored. This is not a general YAML (YAML Ain't Markup Language) loader.

The fixed precedence is:

1. hard governance and safety;
2. explicit user requirements;
3. assigned role contract;
4. project policy;
5. optional policy overlays;
6. task prompt.

This means an overlay can prefer a smaller implementation but cannot delete a mandatory check, bypass a publication gate, expand role authority, or contradict an explicit library requirement.

## Propagation

Every projection is resolved against an exact provider, lane, and target.

The callable resolver requires `explicit` to be a boolean: a string such as `"false"`, an integer, or `None` cannot enable an `explicit-only` projection. Rendering requires `authorizing` to be exactly `False`, not merely a false-like value. These flags do not grant execution or publication authority.

| Target | Lean implementation | Complexity review |
| --- | --- | --- |
| Main agent | Selected implementation lanes | Selected review lanes |
| Internal subagent | Selected implementation lanes | Selected review lanes |
| External worker | Selected implementation lanes | Never |
| External reviewer | Never | Selected review lanes |
| Consultant | Never | Never |

The resolver currently admits Codex and Claude for both built-in policies. Explicit read-only Kimi may receive `complexity-review` on supported review lanes; it never receives implementation policy. Grok remains unavailable in Orchestrarium 1.x.

For external execution, the caller inserts only the applicable rendered frame after the external-governance capsule and role contract, before the task body. The overlay does not select the provider, model, tool list, or service tier.

## Built-in Orchestrarium policies

### Lean implementation

The implementation policy asks an admitted implementer to understand the owner and callers, confirm that new code is needed, reuse repository owners, prefer the standard library and native platform capabilities, avoid a new dependency when an accepted one suffices, and make the smallest coherent general fix. It records a known simplification ceiling and measurable revisit trigger in the existing work-item system rather than creating a second debt tracker.

### Complexity review

The review policy creates a narrow extra opinion that only hunts avoidable complexity: duplicated helpers, unnecessary dependencies, one-implementation abstractions, one-product factories, delegating wrappers, speculative configuration, dead compatibility layers, and removable boilerplate. It is advisory and does not substitute for correctness, security, performance, accessibility, recovery, or publication review.

## Ponytail compatibility

Ponytail is compatible as an external host-managed package, not an Orchestrarium subsystem. Orchestrarium does not vendor Ponytail, execute its JavaScript hooks, install it automatically, manage its `off`/`lite`/`full`/`ultra` modes, or read its private state.

The Orchestrarium installer must preserve unrelated hook entries on shared events, including Ponytail's observed `SessionStart`, `SubagentStart`, and `UserPromptSubmit` entries. It must also preserve unrelated settings, skills, and instruction text. Reinstallation or removal may mutate only artifacts whose Orchestrarium ownership is proven by the existing marker, manifest, exact stock digest, or create-only owner.

The compatibility fixture is based on Ponytail package version `4.9.0` at upstream commit `2ed6c52c9d7e5e56942508591085fd45dea277d3`. This is test provenance, not a runtime dependency or automatic update channel.

## Installation and operation

Install Ponytail with its own provider-supported plugin mechanism. Install Orchestrarium with its existing Codex or Claude installer. Both installation orders, reinstall, update, and owned removal must preserve third-party state. This remains an installer integration acceptance requirement; resolver and catalog tests alone do not establish it. Ponytail remains responsible for its own host/plugin-manager mutations and for preserving unrelated Orchestrarium state.

Orchestrarium does not create optional policy configuration and Version 1.x does not add an always-on overlay hook. Activate the installed `$policy-overlay` skill explicitly; it resolves the user selection, applies project restrictions, and emits only the exact provider/lane/target projection. The resolver may also be invoked directly from the repository root:

```bash
python src.codex/skills/policy-overlay/scripts/policy-overlays.py \
  --provider claude \
  --project-root /path/to/project \
  --home /path/to/home \
  --selection complexity-review \
  --lane review.pre-pr \
  --target external-reviewer \
  --format instructions
```

## Version 1.x and Version 2.x boundary

Version 1.x includes:

- one canonical common skill projected to Codex and Claude;
- a strict local catalog;
- optional user selection and project restriction;
- deterministic provider/lane/target filtering;
- explicit skill or command-line activation;
- bounded instruction rendering for caller-controlled internal and external prompt composition;
- Ponytail-focused installer compatibility regressions as a required integration gate;
- no new runtime dependency.

Deferred to Version 2.x unless independently justified:

- remote policy registries and marketplaces;
- arbitrary executable third-party overlay hooks;
- dependency solving and package lifecycle management;
- dynamic external policy download;
- hot reload;
- a general plugin sandbox;
- automatic synchronization with Ponytail mode state.

## Recovery

Before publication, revert the feature commit or delete the feature branch. After installation, remove `policyOverlays` from the user file or delete the file to restore the previous no-overlay behavior. Orchestrarium-owned installation rollback must not remove Ponytail or unknown third-party state.

## Terms and abbreviations

- **API — Application Programming Interface:** a callable or command-line contract exposed to another component.
- **Lane:** a typed Orchestrarium work category used for provider and policy decisions.
- **Node.js:** the JavaScript runtime used by Ponytail hooks but not required by Orchestrarium.
- **Overlay:** an additional non-authorizing instruction layer.
- **Provider:** the host or external execution system used for a task lane.
- **SessionStart:** a lifecycle event emitted when a provider session starts or resumes.
- **Subagent:** a child agent assigned a narrower task.
- **UTF-8 — Unicode Transformation Format, 8-bit:** Unicode text encoding; an optional leading byte-order mark identifies the encoding, not a configuration key.
- **YAGNI — You Aren't Gonna Need It:** avoiding speculative implementation before a demonstrated requirement.

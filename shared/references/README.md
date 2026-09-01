# Shared References

This directory is the canonical home for repository-wide, design-only reference material shared across provider-specific agent packs.

Use `shared/references/` for:
- shared methodology
- shared governance design
- workflow-selection heuristics
- repository-wide conceptual safety models

Do not use `shared/references/` for:
- install commands
- exact operational runbooks
- pack-specific paths
- pack-specific CLI invocation examples
- platform-specific execution details that belong in runtime pack docs

Exact operational instructions belong in the root repository docs and the corresponding agent pack runtime docs.

Cross-provider dispatch invariants may be named here at design level. For example, provider-backed external CLI launches treat substantive prompt payloads as file-based inputs; exact provider commands and shell syntax stay in runtime pack docs.

Repo-wide source-tree organization rules may also name pack-source-tree paths when the path identity itself is the governed exception (e.g. a grandfathered co-located directory preserved for a documented design constraint such as user-copy/install-script convenience). Exact runtime commands, install runbooks, and CLI invocation syntax still stay in root and pack docs per the rules above; only the path-as-named-exception is in scope here.

For exact provider runtime layout differences such as `global` vs `local` install roots, instruction entrypoints, and native command or extension directories, keep that reference outside `shared/references/`; the current canonical runtime-layout note lives in [`docs/provider-runtime-layouts.md`](../../docs/provider-runtime-layouts.md).

Provider-specific reference trees such as `references-codex/` and `references-claude/` should keep only provider-specific material plus thin compatibility pointers when an older path must remain stable for existing links, reports, or notes.

Shared-core documents may still keep provider-local addenda when the shared blueprint needs runtime-specific concretization. `subagent-operating-model` now follows that pattern: the canonical shared core lives here, while each provider-local tree keeps only its runtime and repository-specific addendum.

`cross-pack-reconciliation.md` is the intentional maintainer-only exception to the pack-specific-path rule above: it maps matching shared semantic blocks across provider contracts. It stays in this canonical reference directory but is excluded from standalone provider branches and packages.

`mcp-continuity.md` defines the shared three-event Model Context Protocol continuity policy. Its Codex and Claude Code addenda own only provider event-envelope, matcher, delivery, and installed-path details.

Russian translations live under `shared/references/ru/` for shared documents that are mirrored for Russian-language operators.

Architecture-pattern selection uses one applicability-first semantic owner and one operator translation:

- [`architecture-pattern-applicability.md`](architecture-pattern-applicability.md) — normative AP0-AP5 routing, disposition, verification, scenarios, diagnostics, and bilingual correspondence matrix.
- [`ru/architecture-pattern-applicability.md`](ru/architecture-pattern-applicability.md) — Russian operator mirror; semantic acceptance remains owned by independent bilingual Architecture Review.

Dynamic user-interface transitions use one causal-continuity semantic owner and one operator translation:

- [`ui-transition-continuity.md`](ui-transition-continuity.md) — sole normative platform-neutral transition classes, continuity dimensions, failure identifiers, settled semantics, portable schema, and metamorphic oracle.
- [`ru/ui-transition-continuity.md`](ru/ui-transition-continuity.md) — required non-authoritative Russian operator mirror; independent bilingual Architecture Review owns semantic-parity acceptance.

Two design-only trunks own independence techniques at different stages: `review-loop-methodology.md` (independence at verification — multiple angles converge on one already-written artifact) and `design-panel-methodology.md` (independence at generation — N independently-framed candidate designs on one pinned problem, converged through one mandatory synthesis, before a single design exists). Installed operative bindings exist for the Claude and Codex production packs. Neither trunk carries exact provider paths or CLI syntax; those live in the corresponding pack binding.

Intentional pack-local exceptions:
- `periodic-control-matrix` stays pack-local because it still embeds provider/runtime vocabulary, task-memory layout, and runtime-doc links rather than a generic shared skeleton.

Provider packs should reuse these shared cross-provider references as a foundation instead of creating another duplicated reference set, but may still need provider-local overlays, wrappers, or vocabulary mapping where a document is not yet fully pack-agnostic.

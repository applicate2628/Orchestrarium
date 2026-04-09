# Shared References

This directory is the canonical home for repository-wide, design-only reference material shared across agent packs.

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

Pack-specific reference trees such as `references-codex/` and `references-claude/` should keep only pack-specific material plus thin compatibility pointers when an older path must remain stable for existing links, reports, or notes.

Shared-core documents may still keep pack-local addenda when the shared blueprint needs runtime-specific concretization. `subagent-operating-model` now follows that pattern: the canonical shared core lives here, while each pack-local tree keeps only its runtime and repository-specific addendum.

Intentional pack-local exceptions:
- `periodic-control-matrix` stays pack-local because it still embeds pack/runtime vocabulary, task-memory layout, and runtime-doc links rather than a generic shared skeleton.

Future packs, including a possible Gemini pack, should reuse these shared references as a foundation instead of creating another duplicated reference set, but may still need pack-local overlays, wrappers, or vocabulary mapping where a document is not yet fully pack-agnostic.

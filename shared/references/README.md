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

For exact provider runtime layout differences such as `global` vs `local` install roots, instruction entrypoints, and native command or extension directories, keep that reference outside `shared/references/`; the current canonical runtime-layout note lives in [`docs/provider-runtime-layouts.md`](../../docs/provider-runtime-layouts.md).

Provider-specific reference trees such as `references-codex/` and `references-claude/` should keep only provider-specific material plus thin compatibility pointers when an older path must remain stable for existing links, reports, or notes.

Shared-core documents may still keep provider-local addenda when the shared blueprint needs runtime-specific concretization. `subagent-operating-model` now follows that pattern: the canonical shared core lives here, while each provider-local tree keeps only its runtime and repository-specific addendum.

Intentional pack-local exceptions:
- `periodic-control-matrix` stays pack-local because it still embeds provider/runtime vocabulary, task-memory layout, and runtime-doc links rather than a generic shared skeleton.

Provider packs, including the current Gemini and Qwen example integrations, should reuse these shared cross-provider references as a foundation instead of creating another duplicated reference set, but may still need provider-local overlays, wrappers, or vocabulary mapping where a document is not yet fully pack-agnostic.

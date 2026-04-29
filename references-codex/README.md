# Codex References

This directory is the provider-local Codex reference tree for the Orchestrarium monorepo.

`shared/references/` holds the canonical shared design cores. `references-codex/` keeps the Codex-specific addenda plus compatibility pointers that still need stable legacy paths.

This tree follows the common provider-local reference layout used across the four branches:

- `README.md`
- `evidence-based-answer-pipeline.md`
- `operating-model-diagram.md`
- `periodic-control-matrix.md`
- `repository-publication-safety.md`
- `repository-task-memory.md`
- `subagent-operating-model.md`
- `workflow-strategy-comparison.md`
- `ru/` translations for the diagram, periodic controls, publication safety, task memory, subagent operating model, and workflow strategy comparison

Use together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs index
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) for shared operator semantics when the Codex line matters
- [../src.codex/README.md](../src.codex/README.md) for the Codex source tree

Provider-backed external CLI prompt delivery inherits the shared file-based prompt rule; use the Codex dispatch docs for the exact Codex-line runtime contract.

Codex skill frontmatter descriptions are startup metadata, not the full role contract. Keep detailed trigger logic and gate rules in each `SKILL.md` body; the Codex validator enforces the compact metadata budget so installed skill catalogs do not overflow the startup skill-description context.

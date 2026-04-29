# Qwen References

This directory is the provider-local Qwen reference tree for the Orchestrarium monorepo.

`shared/references/` holds the canonical shared design cores. `references-qwen/` keeps the Qwen-specific addenda plus compatibility pointers that still need stable legacy paths.

Qwen is maintained here as an explicit example and compatibility integration classified as `WEAK MODEL / NOT RECOMMENDED`. Shipped production `externalProvider: auto` routing remains `codex | claude`; explicit Qwen use is manual example routing only.

This tree follows the common provider-local reference layout used across the provider packs:

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
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) for shared operator semantics when the Qwen line matters
- [../src.qwen/README.md](../src.qwen/README.md) for the Qwen source tree

Provider-backed external CLI prompt delivery inherits the shared file-based prompt rule; use the Qwen dispatch docs for the exact Qwen-line example runtime contract.

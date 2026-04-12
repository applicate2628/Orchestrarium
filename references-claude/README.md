# Claude References

This directory is the provider-local Claude reference tree for the Orchestrarium monorepo.

`shared/references/` holds the canonical shared design cores. `references-claude/` keeps the Claude-specific addenda plus compatibility pointers that still need stable legacy paths.

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
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) for shared operator semantics when the Claude line matters
- [../src.claude/README.md](../src.claude/README.md) for the Claude source tree

# Gemini References

This directory is the provider-local Gemini reference tree for the Orchestrarium monorepo.

Gemini is maintained here as an example-only integration. The repository classifies Gemini as `WEAK MODEL / NOT RECOMMENDED`, so these references document an installable compatibility/example surface rather than a production-recommended auto-routing line.

`shared/references/` holds the canonical shared design cores. `references-gemini/` keeps the Gemini-specific addenda plus compatibility pointers that still need stable legacy paths.

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
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) for shared operator semantics when the Gemini line matters
- [../src.gemini/README.md](../src.gemini/README.md) for the Gemini source tree

Provider-backed external CLI prompt delivery inherits the shared file-based prompt rule; use the Gemini dispatch docs for the exact Gemini-line example runtime contract.

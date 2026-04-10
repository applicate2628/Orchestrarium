# Gemini References

This directory is the required Gemini-side reference tree for the standalone Orchestrarium Gemini branch.

Use it for repository-maintainer methodology and governance references that must remain present in the source branch even though they are not copied into target projects.

Use together with:

- [../README.md](../README.md) for the standalone branch layout
- [../INSTALL.md](../INSTALL.md) for installer and runtime-surface rules
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) for the optional `.gemini/.agents-mode` overlay
- [../src.gemini/](../src.gemini/README.md) for the actual runtime pack surface

This standalone branch intentionally keeps `references-gemini/` self-contained instead of reintroducing the monorepo `shared/` reference layer.

This tree now follows the common provider-local reference layout used across the four branches:

- `README.md`
- `evidence-based-answer-pipeline.md`
- `operating-model-diagram.md`
- `periodic-control-matrix.md`
- `repository-publication-safety.md`
- `repository-task-memory.md`
- `subagent-operating-model.md`
- `workflow-strategy-comparison.md`
- `ru/` translations for the diagram, periodic controls, publication safety, task memory, subagent operating model, and workflow strategy comparison

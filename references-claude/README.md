# Claude References

This directory is the provider-local Claude reference tree for the Orchestrarium monorepo.

`shared/references/` holds the canonical shared design cores. `references-claude/` keeps the Claude-specific addenda plus compatibility pointers that still need stable legacy paths.

This tree follows the common provider-local reference layout used across the four branches:

- `README.md`
- `claude-md-structural-enforcement.md`
- `evidence-based-answer-pipeline.md`
- `mcp-continuity.md`
- `operating-model-diagram.md`
- `periodic-control-matrix.md`
- `repository-publication-safety.md`
- `repository-task-memory.md`
- `subagent-operating-model.md`
- `workflow-strategy-comparison.md`
- `ru/` translations for the evidence pipeline, diagram, periodic controls, publication safety, task memory, subagent operating model, and workflow strategy comparison

Use together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs index
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) for shared operator semantics when the Claude line matters
- [../src.claude/README.md](../src.claude/README.md) for the Claude source tree

Provider-backed external CLI prompt delivery inherits the shared file-based prompt rule; use the Claude dispatch docs for the exact Claude-line runtime contract.

Repository-orientation semantics are shared in `shared/AGENTS.shared.md` and expanded in `shared/references/spine/repository-orientation-and-mechanism-inventory.md`. The Claude Code-specific Bootstrap step 0 and compact operative hook rules live in `src.claude/CLAUDE.md`; [claude-md-structural-enforcement.md](claude-md-structural-enforcement.md) preserves the exhaustive hook behavior, entry-point, installer, removal-command, path, and matcher detail outside the always-loaded entrypoint.

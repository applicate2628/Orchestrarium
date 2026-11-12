# Codex References

This directory is the provider-local Codex reference tree for the Orchestrarium monorepo.

`shared/references/` holds the canonical shared design cores. `references-codex/` keeps the Codex-specific addenda plus compatibility pointers that still need stable legacy paths.

This tree follows the common provider-local reference layout used across the four branches:

- `README.md`
- `evidence-based-answer-pipeline.md`
- `mcp-continuity.md`
- `operating-model-diagram.md`
- `periodic-control-matrix.md`
- `repository-publication-safety.md`
- `repository-task-memory.md`
- `stop-hook-halting-primitives.md`
- `subagent-operating-model.md`
- `workflow-strategy-comparison.md`
- `ru/` translations for the evidence pipeline, diagram, periodic controls, publication safety, task memory, stop-hook halting primitives, subagent operating model, and workflow strategy comparison

Use together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs index
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) for shared operator semantics when the Codex line matters
- [../src.codex/README.md](../src.codex/README.md) for the Codex source tree

Provider-backed external CLI prompt delivery inherits the shared file-based prompt rule; use the Codex dispatch docs for the exact Codex-line runtime contract.

GitHub pull-request review-bot coordination inherits the canonical methodology in [shared/references/github-pr-review-bot-protocol.md](../shared/references/github-pr-review-bot-protocol.md). The installed Codex operative binding is [src.codex/skills/github-pr-review-bot/SKILL.md](../src.codex/skills/github-pr-review-bot/SKILL.md).

Codex skill frontmatter descriptions are startup metadata, not the full role contract. Keep detailed trigger logic and gate rules in each `SKILL.md` body; the Codex validator enforces the compact metadata budget so installed skill catalogs do not overflow the startup skill-description context.

Repository orientation, including its exact evidence record, is owned by `shared/AGENTS.shared.md` and explained in `shared/references/spine/repository-orientation-and-mechanism-inventory.md`. Codex Bootstrap step 0 applies that already-composed shared owner. The inline Bootstrap in `src.codex/AGENTS.codex.md` retains universal verified premises, exact pre-action/pre-fix/pre-commit timing, assumption disclosure, rollback and first-push safeguards, and restoration before dependent decisions or outstanding-result acceptance. Shared evidence, hypothesis, scope, root-cause and indirect-regression owners remain binding; `shared/references/spine/verification-and-decision-discipline.md` explains that joint ownership without becoming an installed runtime dependency.

The separate Codex hook contract remains in `src.codex/AGENTS.codex.md`; its existing mandatory procedure in `src.codex/skills/lead/operating-model.md` owns hook installation, trust, health and matcher details. Hooks are backstops, not substitutes for Bootstrap, and applying Bootstrap does not activate Lead.

## Terms and Abbreviations

- **Bootstrap**: the Codex verified-premise rule and its pre-action, pre-fix and pre-commit checkpoints.
- **CLI**: Command-Line Interface.
- **Lead**: the coordination role; applying shared governance does not activate it.
- **Runtime dependency**: content that must be available to an executing caller, rather than a design-only explanation.

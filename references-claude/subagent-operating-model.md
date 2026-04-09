# Subagent Operating Model — Claude Addendum

> **Note**: this document keeps the Claude-specific addendum to the shared blueprint. The current runtime model uses template-based routing — see `.claude/CLAUDE.md` and `.claude/agents/team-templates/`.

Canonical shared core: [shared/references/subagent-operating-model.md](../shared/references/subagent-operating-model.md)

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This file keeps only Claude-specific runtime and repository concretization for the shared subagent operating model. Use the shared core for canonical blueprint, routing, role, and governance-model text.

## Claude-specific runtime notes

- Claude runtime uses template-based routing and the Agent tool. Treat this file as a local runtime addendum to the shared blueprint, not as the canonical full methodology copy.
- Consultant config lives in `.claude/.agents-mode`; legacy `.claude/.consultant-mode` remains fallback-only during migration.
- Claude-line canonical config does not include `externalClaudeProfile` because Claude-side external dispatch goes to Codex CLI.
- `$external-worker` and `$external-reviewer` dispatch from Claude Code to Codex CLI.

## Claude-side repository concretization

- Adjacent findings and `BLOCKED:prerequisite` go to `work-items/bugs/`.
- Recovery starts at `work-items/index.md`; active items live in `work-items/active/<date>-<slug>/`; archive target is `work-items/archive/<date>-<slug>/`.
- Periodic controls stay pack-local in [periodic-control-matrix.md](periodic-control-matrix.md).
- Claude-side examples use `Gate: PASS | REVISE | BLOCKED:<class> | RETURN(role)`.
- Claude runtime docs also keep the explicit `Artifact invalidation protocol` and `Parallel execution protocol`; use them together with the shared core.

## Shared core now owns

- Main rule, core management rules, delivery loops, routing patterns, role map, prompts, gates, and team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance, and generic task-memory expectations
- The generic lead memo and final wording

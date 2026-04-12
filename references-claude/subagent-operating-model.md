# Subagent Operating Model — Claude Addendum

> **Note**: this document keeps the Claude-specific addendum to the shared blueprint. Canonical routing and operator semantics live in the shared core and the current Claude operator reference surfaces.

Canonical shared core: [shared/references/subagent-operating-model.md](../shared/references/subagent-operating-model.md)

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This file keeps only Claude-specific runtime and repository concretization for the shared subagent operating model. Use the shared core for canonical blueprint, routing, role, and governance-model text.

## Claude-specific runtime notes

- Claude runtime uses the Agent tool and the current Claude operator reference surfaces. Treat this file as a local runtime addendum to the shared blueprint, not as the canonical full methodology copy.
- Consultant config lives in `.claude/.agents-mode`.
- Claude-line canonical config does not include `externalClaudeProfile`; Claude-side `externalProvider: auto` resolves by lane type through the active named priority profile, and explicit provider selection may route eligible external work to Codex CLI, Claude CLI, or Gemini CLI when that route is honest.
- `$external-worker` and `$external-reviewer` dispatch from Claude Code to the provider selected by `.claude/.agents-mode`.

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

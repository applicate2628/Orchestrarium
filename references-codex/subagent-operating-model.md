# Subagent Operating Model — Codex Addendum

Canonical shared core: [shared/references/subagent-operating-model.md](../shared/references/subagent-operating-model.md)

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This file keeps only Codex-specific runtime and repository concretization for the shared subagent operating model. Use the shared core for canonical blueprint, routing, role, and governance-model text.

## Codex-specific runtime notes

- Codex uses sequential skill invocation for native skills. There is no native internal parallel skill dispatch, so internal Codex-role work is still orchestrated sequentially on the Codex line. Independent external adapters may still run in parallel when the routing contract and selected provider runtimes allow it.
- Consultant config lives in `.agents/.agents-mode`.
- Codex may extend the shared `agents-mode` schema with `externalClaudeProfile` to select the Claude CLI execution profile (`sonnet-high` or `opus-max`) when `externalProvider` resolves to Claude.
- `externalProvider: auto` resolves by lane type through the active named priority profile rather than by Codex-line default. Explicit provider selection may still route eligible external work to Claude CLI or Gemini CLI, and documented repo-local visual-routing heuristics may rank Gemini first for image/icon/decorative lanes.

## Codex-side repository concretization

- Adjacent findings and `BLOCKED:prerequisite` use the configured bug-registry path when the repository defines one.
- Task-memory root, recovery entry point, active-item directory, and archive location remain repository-defined in this Codex-side reference model.
- Periodic controls stay pack-local in [periodic-control-matrix.md](periodic-control-matrix.md).
- Older Codex examples may still show `Gate: PASS | REVISE | BLOCKED | RETURN(role)`; the typed `BLOCKED[:class]` form from the shared core remains compatible.

## Shared core now owns

- Main rule, core management rules, delivery loops, routing patterns, role map, prompts, gates, and team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance, and generic task-memory expectations
- The generic lead memo and final wording

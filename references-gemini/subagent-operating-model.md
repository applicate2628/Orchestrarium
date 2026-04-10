# Subagent Operating Model — Gemini Addendum

Canonical shared core: [shared/references/subagent-operating-model.md](../shared/references/subagent-operating-model.md)

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This file keeps only Gemini-specific runtime and repository concretization for the shared subagent operating model. Use the shared core for canonical blueprint, routing, role, and governance-model text.

## Gemini-specific runtime notes

- `src.gemini/GEMINI.md` is the Gemini runtime entrypoint in this monorepo.
- Gemini CLI's built-in `/init` is the canonical way to create or refresh project `GEMINI.md`.
- `.gemini/settings.json` stays the Gemini-native runtime config surface.
- `.gemini/.agents-mode` is an optional Orchestrarium overlay, not a replacement for `.gemini/settings.json`.
- Gemini runtime assets live in `src.gemini/skills/`, `src.gemini/commands/`, and `src.gemini/extension/`.
- The current Gemini scaffold stays sequential and human-steered; do not assume native parallel dispatch.
- Gemini-line `externalProvider: auto` has no standing external default. If Gemini explicitly selects Claude as the external provider, honor `externalClaudeSecretMode`.

## Gemini-side repository concretization

- `references-gemini/` keeps Gemini-specific addenda plus compatibility pointers for the monorepo common layer.
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) is the canonical operator reference when Gemini-line `.gemini/.agents-mode` behavior matters.
- Task-memory root, recovery entry point, active-item directory, and archive location remain repository-defined when tracked task memory is enabled.
- Periodic controls stay pack-local in [periodic-control-matrix.md](periodic-control-matrix.md).

## Shared core now owns

- Main rule, core management rules, delivery loops, routing patterns, role map, prompts, gates, and team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance, and generic task-memory expectations
- The generic lead memo and final wording

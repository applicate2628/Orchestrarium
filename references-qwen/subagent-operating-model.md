# Subagent Operating Model — Qwen Addendum

Canonical shared core: [shared/references/subagent-operating-model.md](../shared/references/subagent-operating-model.md)

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This file keeps only Qwen-specific runtime and repository concretization for the shared subagent operating model. Use the shared core for canonical blueprint, routing, role, and governance-model text.

## Qwen-specific runtime notes

- `src.qwen/QWEN.md` is the Qwen runtime entrypoint in this monorepo.
- `Qwen Code /init` is the canonical way to create or refresh project `QWEN.md`.
- `.qwen/settings.json` stays the Qwen-native runtime config surface.
- `.qwen/.agents-mode.yaml` is the Orchestrarium routing overlay seeded by install, not a replacement for `.qwen/settings.json`.
- Qwen runtime assets live in `src.qwen/skills/`, `src.qwen/commands/`, and `src.qwen/extension/`.
- Orchestrarium installs the pack in the Qwen workspace or user extension tier and leaves top-level `.qwen/skills`, `.qwen/agents`, and `.qwen/commands` available for deliberate overrides.
- The current Qwen source tree stays sequential and human-steered for native internal execution; do not assume native internal parallel dispatch. Independent external adapters may still run in parallel when the routing contract and selected provider runtimes allow it.
- Qwen is an explicit example and compatibility line here, classified as `WEAK MODEL / NOT RECOMMENDED`: shipped production `externalProvider: auto` profiles stay on `codex | claude`.
- Qwen-line `externalProvider: auto` still resolves by lane type through the active named production priority profile rather than by a single Qwen-line default, but the shipped production profile excludes Gemini and Qwen and stays on `codex | claude`.
- Explicit `externalProvider: qwen` is a manual example path only, not a production recommendation.
- On Qwen-line external routing, `externalClaudeApiMode` controls only the supplemental `claude-secret` advisory/review candidate (`disabled | auto | force`, default `auto`); worker lanes must not use it.

## Qwen-side repository concretization

- `references-qwen/` keeps Qwen-specific addenda plus compatibility pointers for the monorepo common layer.
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) is the canonical operator reference when Qwen-line `.qwen/.agents-mode.yaml` behavior matters.
- Task-memory root, recovery entry point, active-item directory, and archive location remain repository-defined when tracked task memory is enabled.
- Periodic controls stay pack-local in [periodic-control-matrix.md](periodic-control-matrix.md).

## Shared core now owns

- Main rule, core management rules, delivery loops, routing patterns, role map, prompts, gates, and team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance, and generic task-memory expectations
- The generic lead memo and final wording

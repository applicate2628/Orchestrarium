# Subagent Operating Model — Claude Addendum

> **Note**: this document keeps the Claude-specific addendum to the shared blueprint. Canonical routing and operator semantics live in the shared core and the current Claude operator reference surfaces.

Canonical shared core: [shared/references/subagent-operating-model.md](../shared/references/subagent-operating-model.md)

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This file keeps only Claude-specific runtime and repository concretization for the shared subagent operating model. Use the shared core for canonical blueprint, routing, role, and governance-model text.

## Claude-specific runtime notes

- Claude runtime uses the Agent tool and the current Claude operator reference surfaces. Treat this file as a local runtime addendum to the shared blueprint, not as the canonical full methodology copy.
- Claude native Agent lanes use the shared rolling lane-ready-set contract. Current host capacity is authoritative when exposed; otherwise admission probes one ranked candidate at a time and does not cache a numeric cap.
- Claude native role definitions provide fixed installed profiles and default effort floors unless the host explicitly supports a per-launch override and confirms it in returned runtime metadata.
- Consultant config lives in `.claude/.agents-mode.yaml`.
- Claude-line canonical config does not include `externalClaudeProfile`; Claude-side `externalProvider: auto` resolves by lane type through the active named production priority profile and shipped production `auto` uses `codex | claude` only. Explicit Kimi selection is limited to policy-admitted read-only work; Grok remains unavailable, and removed Gemini/Qwen scalar values fail closed with `E_EXTERNAL_PROVIDER_REMOVED`.
- `$external-worker` and `$external-reviewer` dispatch from Claude Code to the provider selected by `.claude/.agents-mode.yaml`.

## Claude-side repository concretization

- Adjacent findings and `BLOCKED:prerequisite` go to `work-items/bugs/`.
- Human recovery starts at generated `work-items/README.md`; state resolves from physical `work-items/backlog/`, `work-items/active/<date>-<slug>/`, and `work-items/archive/YYYY-MM/<date>-<slug>/` locations plus owning artifacts. `work-items/index.md` is compatibility-only.
- Periodic controls stay pack-local in [periodic-control-matrix.md](periodic-control-matrix.md).
- Claude-side examples use `Gate: PASS | REVISE | BLOCKED:<class> | RETURN(role)`.
- Claude runtime docs also keep the explicit `Artifact invalidation protocol` and `Parallel execution protocol`; use them together with the shared core.

## Shared core now owns

- Main rule, core management rules, delivery loops, routing patterns, role map, prompts, gates, and team composition
- Shared review/gate semantics, periodic-controls model, rolling lane-ready admission, parallel-work guidance, and generic task-memory expectations
- The generic lead memo and final wording

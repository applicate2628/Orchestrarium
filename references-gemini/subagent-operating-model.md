# Subagent Operating Model - Gemini Reference

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This standalone branch keeps one Gemini-local operating-model reference instead of splitting methodology across shared and provider-local layers.

## Gemini runtime notes

- `GEMINI.md` is the Gemini runtime entrypoint.
- Gemini CLI's built-in `/init` is the canonical way to create or refresh project `GEMINI.md`.
- `.gemini/settings.json` stays the Gemini-native runtime config surface.
- `.gemini/.agents-mode` is an optional Orchestrarium overlay, not a replacement for `.gemini/settings.json`.
- Skills live in `skills/<name>/SKILL.md`.
- User-invoked command helpers live in `commands/**/*.toml`.
- The current pack surface stays sequential and human-steered; do not assume native parallel dispatch.

## Delivery model

- `$lead` coordinates approved work and keeps the pipeline staged: `Research -> Design -> Plan -> Implement -> Review/QA/Security`.
- Factual roles come before interpretive ones.
- Accepted artifacts, not raw transcripts, are passed downstream.
- `PASS` advances, `REVISE` stays local for up to 3 cycles, and `BLOCKED` is reserved for real external blockers.

## Gemini-side repository concretization

- `references-gemini/` is the required standalone reference tree.
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) is the canonical operator reference for `.gemini/.agents-mode`.
- Task-memory root, recovery entry point, active-item directory, and archive location remain repository-defined when task memory is enabled.
- Periodic controls live in [periodic-control-matrix.md](periodic-control-matrix.md).
- Publication safety lives in [repository-publication-safety.md](repository-publication-safety.md).
- If Gemini routes eligible external work to Claude CLI, `externalClaudeSecretMode` controls whether Claude secret env injection is automatic on limit fallback or forced for the primary call.

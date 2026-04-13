# Subagent Operating Model - Gemini Reference

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This standalone branch keeps one Gemini-local operating-model reference as an addendum. Canonical operator truth for `.gemini/.agents-mode`, the accepted init-time preset family, the shared lane matrix, and Claude transport semantics lives in [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md).

## Gemini runtime notes

- `GEMINI.md` is the Gemini runtime entrypoint.
- Gemini CLI's built-in `/init` is the canonical way to create or refresh project `GEMINI.md`.
- `.gemini/settings.json` stays the Gemini-native runtime config surface.
- `.gemini/.agents-mode` is the Orchestrarium routing overlay seeded by install, not a replacement for `.gemini/settings.json`.
- The accepted init-time preset family is `default`, `absolute-balance`, `external-aggressive`, `correctness-first`, and `max-speed`. These are init shortcuts only; the preset name is not persisted after expansion into canonical keys.
- Skills live in `skills/<name>/SKILL.md`.
- User-invoked command helpers live in `commands/**/*.toml`.
- The current pack surface stays sequential and human-steered for native internal execution; do not assume native internal parallel dispatch. Independent external adapters may still run in parallel when the routing contract and selected provider runtimes allow it. If native internal slot or thread limits would otherwise block independent eligible lanes, prefer available external adapters over silent serialization or dropping a lane.

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
- `externalProvider: auto` keeps the active named priority profile as the routing source, while documented repo-local visual-routing heuristics may still prefer Gemini itself for image, icon, decorative visual, and other clearly visual lanes.
- `.gemini/.agents-mode` may carry `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`; the shipped profiles are `balanced` and `gemini-crosscheck`.
- If Gemini routes eligible external work to Gemini itself through an explicit self-provider override, honor `externalModelMode` first. Under `runtime-default`, leave Gemini on its runtime default model/profile. Under `pinned-top-pro`, honor `externalGeminiFallbackMode`: stay on `gemini-3.1-pro` when disabled, allow one retry on `gemini-3-flash` when `auto`, and do not silently drop below Gemini 3.
- The current shared lane taxonomy includes `review.performance-architecture`, `worker.systems-performance-implementation`, `worker.ui-structural-modernization`, and `worker.ui-surgical-patch-cleanup` alongside the older advisory, review, implementation, long-autonomous, visual, and decorative lanes.
- `externalOpinionCounts` are lane-local distinct-opinion requirements, not a cap on how many same-provider helper instances may run in parallel across disjoint slices; bounded helper batches use `external-brigade`.
- If Gemini routes eligible external work to Claude, honor both `externalClaudeSecretMode` and `externalClaudeApiMode`; `claude-api` remains a Claude transport, not a separate provider.

# Plan

This rewrite is intentionally split into one shared canonical freeze plus three parallel-safe provider mirror families, then a final validation and independent architecture gate.

## 1. Shared/Main Canonical Freeze
- Scope: `AGENTS.shared.md`, `AGENTS.md`, `docs/agents-mode-reference.md`, `docs/external-worker-design.md`, `shared/references/subagent-operating-model.md`, `shared/references/ru/subagent-operating-model.md`, `docs/provider-runtime-layouts.md`, `INSTALL.md`, `README.md`, and any shared/main wording that still claims a line-default provider or a single mandatory consultant-check.
- Allowed change surface: add the additive `externalPriorityProfile` / `externalPriorityProfiles` / `externalOpinionCounts` schema, keep `externalProvider` scalar semantics intact, keep `claude-api` as a Claude transport, and pluralize closeout wording to "one or more external consultant-checks" where lane policy requires it.
- Must not break: current provider universe `auto | codex | claude | gemini`, existing scalar override behavior, current file inventories, and pack-install shape.
- Acceptance criteria: shared/main docs describe the new schema and defaults (`balanced`, current shared lane matrix, count default `1`), no stale line-default or single-check wording remains, and the canonical routing story is consistent across the shared refs.
- Validation: targeted stale-wording scan, `git diff --check`, and a quick readback of the updated shared reference paragraphs.
- Rollback note: revert only the shared/main doc family if the canonical schema wording needs correction.

## 2. Provider Mirror Family A: Codex
- Scope: `src.codex/AGENTS.codex.md`, `src.codex/skills/init-project/SKILL.md`, `src.codex/skills/consultant/SKILL.md`, `src.codex/skills/external-worker/SKILL.md`, `src.codex/skills/external-reviewer/SKILL.md`, `src.codex/skills/second-opinion/SKILL.md`, `src.codex/skills/lead/external-dispatch.md`, `src.codex/skills/lead/operating-model.md`, `src.codex/skills/lead/subagent-contracts.md`, `INSTALL.md`, and the standalone `codex/` mirror equivalents plus Codex validator scripts.
- Dependencies: starts only after Phase 1 freezes the shared canonical wording.
- Allowed change surface: mirror the new schema keys, the profile-based `auto` resolution, the pluralizable consultant closeout rule, and the broader Gemini participation wording where applicable; refresh Codex validator hash pins for shared-reference text that changed.
- Must not break: Codex-specific transport/profile semantics, required file inventories, and the existing scalar `externalProvider` override path.
- Acceptance criteria: Codex main and standalone mirrors agree on the new schema and routing language, validator hash pins match the updated shared references, and no stale "host-default" or one-check-only wording remains.
- Validation: Codex validator in both trees, `git diff --check`, and targeted stale-wording scans across the Codex family.
- Rollback note: revert the Codex family and its validator hash pins together if the mirror diverges.

## 3. Provider Mirror Family B: Claude
- Scope: `src.claude/CLAUDE.md`, `src.claude/commands/agents-init-project.md`, `src.claude/commands/agents-help.md`, `src.claude/commands/agents-second-opinion.md`, `src.claude/agents/consultant.md`, `src.claude/agents/external-worker.md`, `src.claude/agents/external-reviewer.md`, `src.claude/agents/contracts/external-dispatch.md`, `src.claude/agents/contracts/operating-model.md`, `src.claude/agents/contracts/subagent-contracts.md`, `INSTALL.md`, and the standalone `claude/` mirror equivalents plus Claude validator scripts.
- Dependencies: starts only after Phase 1 freezes the shared canonical wording.
- Allowed change surface: mirror the additive schema and switchable priority-profile semantics, keep `claude-api` as Claude transport only, preserve explicit scalar override behavior, and pluralize closeout semantics where lane policy asks for more than one opinion.
- Must not break: Claude-line canonical config shape, provider universe, and required file inventories.
- Acceptance criteria: Claude main and standalone mirrors describe the same profile-based `auto` routing, the broader Gemini participation wording is present where relevant, and validator hash pins are refreshed for any changed shared-reference text.
- Validation: Claude validator in both trees, `git diff --check`, and targeted stale-wording scans across the Claude family.
- Rollback note: revert the Claude family and its validator hash pins together if the mirror diverges.

## 4. Provider Mirror Family C: Gemini
- Scope: `src.gemini/skills/init-project/SKILL.md`, `src.gemini/skills/consultant/SKILL.md`, `src.gemini/skills/external-worker/SKILL.md`, `src.gemini/skills/external-reviewer/SKILL.md`, `src.gemini/skills/second-opinion/SKILL.md`, `src.gemini/skills/lead/external-dispatch.md`, `src.gemini/skills/lead/operating-model.md`, `src.gemini/skills/lead/subagent-contracts.md`, `src.gemini/commands/agents/help.toml`, `src.gemini/commands/agents/init-project.toml`, `INSTALL.md`, and the standalone `gemini/` mirror equivalents.
- Dependencies: starts only after Phase 1 freezes the shared canonical wording.
- Allowed change surface: broaden Gemini beyond the visual-only heuristic so it can participate in advisory/review roles when the active profile ranks it inside the requested opinion count, while keeping explicit `gemini` as a scalar override and leaving `claude-api` as Claude transport only.
- Must not break: Gemini runtime entrypoint shape, `.gemini/settings.json` ownership, and the preview `agents/` surface inventory.
- Acceptance criteria: Gemini main and standalone mirrors reflect the same profile-based routing and multi-opinion semantics, no stale "ordinary work defaults to Claude" wording remains, and Gemini participation outside visual lanes is described honestly.
- Validation: Gemini validator in both trees, `git diff --check`, and targeted stale-wording scans across the Gemini family.
- Rollback note: revert the Gemini family independently if the broader participation wording needs to be reconsidered.

## 5. Final Validation And Gate
- Scope: all four trees together after Phases 1-4 are complete.
- Acceptance criteria: every repo-family validator passes, all targeted stale-wording scans are clean, Codex and Claude hash pins are refreshed, and the combined diff is coherent with the accepted design.
- Required gate: `$architecture-reviewer` must inspect the combined control-plane diff and return `PASS` before the item can move to closeout.
- Failure handling: if validation fails, return to the smallest affected provider family or shared/main canonical file set instead of widening scope.

Recommended next role sequence: `$lead` accepts Phase 1, then the Codex, Claude, and Gemini mirror phases run in parallel, then `$lead` runs final validation and hands the combined diff to `$architecture-reviewer`.

PASS

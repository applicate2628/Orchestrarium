# Canonical Brief

## Goal

Finish the current Orchestrarium cross-provider refresh so `main`, `claude`, `gemini`, and `codex` all reflect the same accepted governance and provider-specific source of truth, while bringing Gemini up to an official-preferred runtime model and extending the external-provider story to cover Gemini invocation from Codex or Claude.

## Scope

- Restore canonical `work-items/` continuity for the in-flight batch.
- Close or archive stale active work items that are already complete.
- Update Gemini source surfaces to reflect official-preferred runtime entry, built-in `/init`, and provider-local runtime state expectations.
- Define and implement the minimum safe Gemini-side operator-state and external-invocation support required for Orchestrarium.
- Synchronize the provider-specific source trees across `Orchestrarium`, `claude`, `gemini`, and `codex`.
- Run global audit, external opinions, and targeted performance/effectiveness checks before closeout.

## Out of Scope

- Publishing or pushing changes.
- Inventing a non-official Gemini runtime tree when official Gemini surfaces already cover the need.
- Replacing mandatory internal reviewers in risk-sensitive templates.
- Reworking unrelated shared references beyond the minimum needed to keep this batch coherent.

## Acceptance Criteria

- A current work item in `work-items/active/` tracks this batch with `roadmap.md`, `brief.md`, `status.md`, and `plan.md`.
- Stale completed active items are closed with `closure.md` and moved out of `work-items/active/`.
- Gemini documentation and validation reflect official runtime facts, including built-in `/init` and `.gemini/settings.json`.
- The accepted operator-mode and external-dispatch semantics cover Gemini where intended, without duplicating conflicting source-of-truth tables.
- Standalone `claude`, `gemini`, and `codex` branches are resynced to the intended provider-specific source of truth with minimal clean diffs.
- Relevant validation commands pass.
- External review opinions and targeted effectiveness/performance notes are recorded before closure.

## Required Roles

- `$knowledge-archivist` for task-memory continuity and archival hygiene.
- `$lead` for routing, integration ownership, and gate control.
- Provider-specific implementation ownership for `src.gemini`, shared docs, and standalone branch sync.
- External reviewers for independent opinions on the merged result.

## Critical Risks

- Gemini changes drift away from official runtime behavior by inventing unnecessary repo-local layers.
- Shared operator-mode semantics diverge across providers.
- Standalone branches stay semantically stale even if `main` becomes correct.
- Current work remains untracked in canonical task memory, weakening recovery and publication readiness.

## Current Stage

- Research / design and task-memory recovery


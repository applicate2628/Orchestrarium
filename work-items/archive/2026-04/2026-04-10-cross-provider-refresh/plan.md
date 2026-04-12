# Implementation Plan

## Phase 1 — Task-memory recovery

- Create the current admitted work item in `work-items/active/`.
- Add `closure.md` to stale completed active items.
- Move closed items into `work-items/archive/2026-04/`.

## Phase 2 — Gemini runtime and provider-state design

- Confirm official Gemini runtime surfaces and non-interactive CLI invocation.
- Keep official initialization centered on built-in `/init`.
- Decide the minimum Orchestrarium-specific operator-state layer needed beyond `.gemini/settings.json`.

## Phase 3 — Main repository implementation

- Update `src.gemini/`, shared operator-mode docs, and provider-runtime docs.
- Extend external-dispatch semantics where Gemini invocation must be supported from Codex or Claude.
- Keep root manuals and release notes aligned.

## Phase 4 — Standalone branch resync

- Resync `gemini` to the accepted Gemini source of truth.
- Resync `codex` to the accepted Codex source of truth.
- Resync `claude` only where the provider source of truth on `main` changed and does not reintroduce obsolete surfaces.

## Phase 5 — Audit and closeout

- Run provider validators.
- Run targeted smoke tests and note effectiveness/performance observations.
- Collect external review opinions.
- Update `status.md`, prepare closure, and stop before publication.


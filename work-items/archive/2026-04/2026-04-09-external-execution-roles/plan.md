# Implementation Plan

## Phase 1

Update shared governance and root docs so the role model explicitly distinguishes:

- `$consultant` as advisory-only
- `$external-worker` as explicit implementation-only external executor
- `$external-reviewer` as explicit review-only external audit lane

## Phase 2

Implement Codex-pack support:

- add new skills
- update role/routing/contracts docs
- keep reviewer and consultant boundaries intact

## Phase 3

Implement Claude-pack support:

- add new agent roles
- update CLAUDE routing, help, commands, contracts, and validator coverage
- keep new roles explicit and opt-in

## Phase 4

Verify integrated behavior:

- Codex validation
- Claude validation
- Codex installer dry-run in global and target modes
- Claude installer dry-run in global and target modes


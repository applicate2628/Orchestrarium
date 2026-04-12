# Canonical Brief

## Goal

Add `$external-worker` and `$external-reviewer` to both packs as explicit cross-provider execution roles while keeping `$consultant` advisory-only.

## Scope

- Shared governance updates for the new role model.
- Codex-pack implementation of `external-worker` and `external-reviewer`.
- Claude-pack implementation of `external-worker` and `external-reviewer`.
- Routing, contracts, role maps, validators, and user-facing docs required to make the roles usable and structurally valid.

## Out of Scope

- Replacing mandatory internal reviewers with external reviewers.
- Adding new slash commands or toggle files for the new roles.
- Expanding `$consultant` into an execution or review role.
- Changing existing reviewer or implementer semantics beyond explicit external-role support.

## Acceptance Criteria

- Both packs expose direct user-callable `external-worker` and `external-reviewer` roles.
- `external-worker` is implementation-only and requires an assigned implementer role from the allowed set.
- `external-reviewer` is review-only, requires an assigned reviewer role from the allowed set, and requires `Review strategy: adversarial`.
- Both roles fail fast on unavailable external provider; no silent or automatic fallback to internal roles.
- `$consultant` remains advisory-only and separate from these execution paths.
- Codex and Claude validation commands pass.
- Codex and Claude installer dry-runs pass in global and target modes.

## Required Roles

- `$knowledge-archivist` for task-memory and repository knowledge hygiene.
- Codex-pack implementation specialist.
- Claude-pack implementation specialist.
- `$qa-engineer` for integrated verification.

## Critical Risks

- Governance drift between shared/routing docs and per-role contracts.
- Accidental overlap with `$consultant` or mandatory internal reviewer semantics.
- Validation or installer breakage due to new role additions.

## Current Stage

- Implement


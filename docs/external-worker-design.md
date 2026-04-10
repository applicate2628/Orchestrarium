# External Worker & External Reviewer — Design Spec

**Date:** 2026-04-09
**Status:** Approved
**Scope:** Orchestrarium skill-pack (Claude Code + Codex packs)

## Problem

The current role architecture has no universal implementer or reviewer that works through an external CLI provider. Every implementation task requires selecting a domain-specific specialist (backend-engineer, frontend-engineer, etc.), even when the task is simple/mechanical or the external CLI is better suited. There is no "economy mode" toggle to prefer external dispatch for cost or workflow reasons.

## Decision

Introduce two new roles and a shared dispatch module:

- `$external-worker` — universal implementer via external CLI
- `$external-reviewer` — universal reviewer/QA via external CLI
- `external-dispatch.md` — shared CLI dispatch protocol (DRY, used by consultant + both new roles)

## New roles

### `$external-worker`

| Property | Value |
|----------|-------|
| File | `src.claude/agents/external-worker.md` |
| Stages | `implement` |
| Replaces | Domain-specific implementers (backend-engineer, frontend-engineer, qt-ui-engineer, toolchain-engineer, data-engineer, geometry-engineer, graphics-engineer, visualization-engineer, platform-engineer, model-view-engineer) |
| Interaction type | `DIRECT` (standard implementer) |
| Input contract | Accepted upstream artifacts (research, design, plan) — same as domain specialists |
| Output contract | Implementation package + standard gate (`PASS \| REVISE \| BLOCKED`) |
| Execution | External CLI dispatch only. No internal fallback. If CLI unavailable — role is disabled. |
| Domain scope | Unrestricted. Works in any domain — determined by the task. |

### `$external-reviewer`

| Property | Value |
|----------|-------|
| File | `src.claude/agents/external-reviewer.md` |
| Stages | `review` + `QA` |
| Replaces | Domain-specific reviewers (architecture-reviewer, performance-reviewer, security-reviewer, ux-reviewer, accessibility-reviewer, ui-test-engineer) + qa-engineer |
| Interaction type | `DIRECT` (standard reviewer) |
| Input contract | Implementation artifact from the implement stage |
| Output contract | Review findings / QA verdict + standard gate (`PASS \| REVISE \| BLOCKED`) |
| Execution | External CLI dispatch only. No internal fallback. If CLI unavailable — role is disabled. |
| Separation of concerns | Worker implements, reviewer verifies. No conflict of interest. |

## Shared dispatch module

### File

| Pack | Path |
|------|------|
| Claude Code | `src.claude/agents/contracts/external-dispatch.md` |
| Codex | Corresponding location in `src.codex/` (e.g., `skills/lead/external-dispatch.md`) |

### Consumers

- `consultant.md` — refactored to reference this module instead of inline dispatch
- `external-worker.md` — references this module
- `external-reviewer.md` — references this module

### Contents

Full value-by-value operator semantics now live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md). Keep this design spec at the decision level and let the dedicated reference own the complete `value | meaning` tables.

1. **Config file location**

   | Platform | Path |
   |----------|------|
   | Claude Code | `.claude/.agents-mode` (legacy `.claude/.consultant-mode` fallback) |
   | Codex | `.agents/.agents-mode` (legacy `.agents/.consultant-mode` fallback) |

2. **Extended config format**

   ```
   consultantMode: external
   delegationMode: manual
   mcpMode: auto
   preferExternalWorker: true
   preferExternalReviewer: true
   externalClaudeProfile: sonnet-high
   ```

   - `consultantMode` — consultant-only mode: `external`, `auto`, `internal`, `disabled`
   - `delegationMode` — `manual`, `auto`, or `force` team delegation
   - `mcpMode` — `auto` vs `force` MCP routing policy
   - `preferExternalWorker` — external-worker as default on `implement` stage
   - `preferExternalReviewer` — external-reviewer as default on `review` + `QA` stages
   - `externalClaudeProfile` — Codex-line only optional Claude CLI execution profile: `sonnet-high` or `opus-max`
   - Each toggle is independent
   - Default full shape on first creation: `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`; Codex also writes `externalClaudeProfile: sonnet-high`

3. **Dispatch protocol (platform-dependent)**

   | Context | External CLI | Command |
   |---------|-------------|---------|
   | Claude Code calling external | Codex | `codex --quiet --full-auto "$PROMPT"` |
   | Codex calling external | Claude CLI | `printf '%s' "$PROMPT" \| claude -p --effort high --permission-mode bypassPermissions` |

   Each pack calls the *other* CLI as the external provider.

4. **Common rules**
   - CLI availability check before dispatch (`which codex` / `where codex` on Claude Code; `claude` / `claude.exe` on Codex)
   - Hard tasks: `--model gpt-5.4 --reasoning-effort xhigh` (Codex) or `--effort high` (Claude CLI)
   - Timeout: 5-15 minutes before treating a run as stalled
   - Provenance header mandatory for all three roles:
     - **Requested mode:** `<external | auto | internal>`
     - **Actual execution path:** `<external CLI (provider name) | internal subagent | role-play (violation)>`
     - **Deviation reason:** `<none | external unavailable: [reason] | fallback approved by user>`

## Routing rules

### When toggles are ON

The orchestrator (lead or main conversation) **prefers** external roles by default:

- `consultantMode: external | auto | internal | disabled` — consultant-only behavior
- `delegationMode: manual | auto | force` — `manual` keeps explicit-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist
- `mcpMode: auto | force` — `auto` uses MCP by judgment; `force` treats relevant MCP use as an explicit standing instruction
- `preferExternalWorker: true` — `$external-worker` on `implement` stage
- `preferExternalReviewer: true` — `$external-reviewer` on `review` + `QA` stages
- `externalClaudeProfile: sonnet-high | opus-max` — Codex-line only; when Codex dispatches to Claude CLI, prefer the matching model/effort profile instead of the provider default

Domain specialist is selected instead only when:

1. Task objectively requires deep domain expertise (algorithms, geometry, security-sensitive)
2. Template **mandates** a specific reviewer (e.g., `security-reviewer` in `security-sensitive` template — safety gate, not replaceable)
3. Orchestrator explicitly justifies the choice

### When toggles are OFF

Standard behavior. External roles available only by explicit user request.

### Selection criteria for orchestrator

| Criterion | Route to |
|-----------|----------|
| Task is simple / mechanical | `$external-worker` / `$external-reviewer` |
| External CLI better suited for the task | `$external-worker` / `$external-reviewer` |
| User explicitly requested | `$external-worker` / `$external-reviewer` |
| Deep domain expertise required | Domain specialist |

### User override

Always available in both directions, regardless of toggle state.

### CLI unavailable

Normal routing fallback to domain specialist. Not an error — standard routing behavior.

## Affected files

| File | Change |
|------|--------|
| `src.claude/agents/external-worker.md` | **New** — implementer role |
| `src.claude/agents/external-reviewer.md` | **New** — reviewer/QA role |
| `src.claude/agents/contracts/external-dispatch.md` | **New** — shared CLI dispatch |
| `src.claude/agents/consultant.md` | **Refactor** — inline CLI dispatch replaced with reference to external-dispatch.md |
| `src.claude/CLAUDE.md` | **Update** — role index + routing rules + delegation decision tree |
| `src.claude/agents/contracts/operating-model.md` | **Update** — routing rules for external roles |
| `src.claude/agents/contracts/subagent-contracts.md` | **Update** — mention new roles |
| Team templates (JSON) | **No change** — substitution via routing decision, not template entries |
| `src.codex/` (mirror) | **Analogous changes** — external-worker SKILL.md, external-reviewer SKILL.md, dispatch protocol, consultant refactor, governance updates |

## Constraints

- `$external-worker` and `$external-reviewer` must never be the same agent instance on the same task (separation of concerns)
- Mandatory reviewers in risk-sensitive templates (`security-reviewer` in `security-sensitive`, `performance-reviewer` in `performance-sensitive`) are NOT replaceable by `$external-reviewer`
- No internal subagent fallback for external roles — either external CLI works or role is disabled
- Existing `.consultant-mode` files continue to work as legacy fallback input. First-write upgrade should migrate them into `.agents-mode`, map legacy `mode` to `consultantMode`, default missing `delegationMode` to `manual`, default missing `mcpMode` to `auto`, and on the Claude line drop any inert `externalClaudeProfile` value instead of carrying it forward.

## Non-goals

- Changing team template JSON structure
- Replacing the consultant's advisory-only contract
- Adding new interaction types to the operating model
- Auto-detection of when external worker is "better" — orchestrator uses explicit criteria

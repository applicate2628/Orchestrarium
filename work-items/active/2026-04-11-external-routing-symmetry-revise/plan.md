# Plan

- Goal: align `Orchestrarium/main`, `codex`, `claude`, and `gemini` on one truthful external-routing model and one common worker/reviewer role principle.
- Guardrails:
  - keep the shared provider universe `auto | codex | claude | gemini`
  - `externalProvider: auto` resolves by lane type through the shared matrix, not by host-line default
  - self-provider execution is explicit-override only
  - `claude-api` stays a Claude transport, not a separate provider
  - `$external-worker` covers the full worker-side lane
  - `$external-reviewer` covers the review / QA lane
  - Gemini remains first-choice for image, icon, and decorative visual lanes when that routing is honest

## Phase 1 — Canonical Routing Freeze

- Scope:
  - `Orchestrarium/docs/agents-mode-reference.md`
  - `Orchestrarium/README.md`
  - `Orchestrarium/INSTALL.md`
  - `Orchestrarium/src.codex/skills/lead/external-dispatch.md`
  - `Orchestrarium/src.claude/agents/contracts/external-dispatch.md`
  - `Orchestrarium/src.gemini/skills/lead/external-dispatch.md`
  - standalone mirror docs and external-dispatch contracts in `codex/`, `claude/`, `gemini/`
- Acceptance:
  - shared provider universe documented everywhere
  - lane matrix documented everywhere
  - self-provider rule explicit
  - no remaining line-default-provider claims in Phase 1 surfaces
- Status: accepted, with downstream mirror/materialization follow-up required

## Phase 2A — Codex Materialization

- Scope:
  - `Orchestrarium/src.codex/AGENTS.codex.md`
  - `Orchestrarium/src.codex/skills/external-worker/SKILL.md`
  - `Orchestrarium/src.codex/skills/external-reviewer/SKILL.md`
  - `Orchestrarium/src.codex/skills/second-opinion/SKILL.md`
  - `Orchestrarium/src.codex/skills/lead/subagent-contracts.md`
  - standalone `codex/INSTALL.md`
  - standalone Codex mirrors for the same logical surfaces
- Acceptance:
  - no Codex-line default-provider wording remains
  - Codex pack speaks in shared-universe / lane-matrix terms only

## Phase 2B — Claude Materialization

- Scope:
  - `Orchestrarium/src.claude/CLAUDE.md`
  - `Orchestrarium/src.claude/commands/agents-second-opinion.md`
  - `Orchestrarium/src.claude/agents/consultant.md`
  - `Orchestrarium/src.claude/agents/external-worker.md`
  - `Orchestrarium/src.claude/agents/external-reviewer.md`
  - `Orchestrarium/src.claude/agents/contracts/operating-model.md`
  - `Orchestrarium/src.claude/agents/contracts/subagent-contracts.md`
  - standalone Claude mirrors and `claude/INSTALL.md`
- Acceptance:
  - no Claude-line default-provider wording remains
  - Claude transport keys are described truthfully as transport-only after provider resolution to Claude

## Phase 2C — Gemini Materialization

- Scope:
  - `Orchestrarium/src.gemini/skills/init-project/SKILL.md`
  - `Orchestrarium/src.gemini/skills/consultant/SKILL.md`
  - `Orchestrarium/src.gemini/skills/external-worker/SKILL.md`
  - `Orchestrarium/src.gemini/skills/external-reviewer/SKILL.md`
  - `Orchestrarium/src.gemini/skills/second-opinion/SKILL.md`
  - `Orchestrarium/src.gemini/skills/lead/subagent-contracts.md`
  - standalone Gemini mirrors
- Acceptance:
  - no Gemini-line default-provider wording remains
  - Gemini visual-first heuristic stays truthful without pretending ordinary `auto` self-selects Gemini on the Gemini line

## Phase 2D — Shared / Main Reference Reconciliation

- Scope:
  - `Orchestrarium/AGENTS.md`
  - `Orchestrarium/cross-pack-reconciliation.md`
  - `Orchestrarium/docs/external-worker-design.md`
  - `Orchestrarium/shared/references/subagent-operating-model.md`
  - `Orchestrarium/shared/references/ru/subagent-operating-model.md`
- Acceptance:
  - shared references no longer describe line-default providers
  - role-lane semantics match the accepted canon and pack-local contracts

## Phase 3 — Validation And Residual Drift Audit

- Checks:
  - `git diff --check` on all touched trees
  - `bash ./src.codex/skills/lead/scripts/validate-skill-pack.sh` in `Orchestrarium`
  - `bash ./src.claude/agents/scripts/validate-skill-pack.sh` in `Orchestrarium`
  - `bash ./src.gemini/scripts/validate-pack.sh .` in `Orchestrarium`
  - standalone `codex`, `claude`, `gemini` validators as applicable
  - targeted `rg` audit for stale line-default-provider phrases and stale external-role restrictions
- Exit criteria:
  - docs, init/help surfaces, skill contracts, and shared references agree
  - residual asymmetries are either fixed or explicitly recorded as deferred non-blockers

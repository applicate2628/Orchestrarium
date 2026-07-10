---
name: lead
description: Coordinate Qwen-line work through the same shared role vocabulary used by the Codex and Claude packs. Use when Qwen Code needs an orchestration owner for research, design, planning, implementation, QA, and review without collapsing specialist roles into the main conversation.
---

# Lead

Use `$lead` as the Qwen-line orchestration owner.

This pack carries the same role vocabulary as the neighboring packs as the universal Qwen `skills/` catalog — one skill per role, the cross-tool surface read by Qwen Code and the wider Antigravity/Gemini-CLI skill ecosystem.

## Core rule

Orchestrarium keeps orchestration in the main Qwen session so routing, stage gates, and accepted-artifact handling stay explicit.

That means:

- the main session owns routing, stage gates, and task continuity
- specialist execution happens by activating the matching role skill in `../../<role>/SKILL.md` (dispatched as a subagent where the runtime supports skill-backed subagents, activated in-session otherwise)
- `team-templates/*.json` is the repo-local team map for the common role principle
- the lead skill is the canonical orchestration contract for the whole role catalog

## Bootstrap — first action

> **DO NOT implement.** When receiving a request or delegation, execute in order:

1. **Verify work-items task memory (ENFORCED)** — for non-trivial lead-managed work, the default repository task-memory root is `work-items/`:
   - Check `work-items/active/` for existing items. For each active item, verify: `roadmap.md` exists and is current, `brief.md` has scope/owners/stage, and `status.md` has current snapshot.
   - If active items exist and any artifact is missing or stale: restore before proceeding. For multiple active items or complex recovery state, invoke `$knowledge-archivist` for a completeness audit before continuing.
   - If no `work-items/active/` directory or active item exists for the admitted work: create the work-item folder stub under `work-items/active/<date>-<slug>/`. Step 3 populates lead-owned artifacts.
   - Do not treat "no local init" or "no pre-existing work-items directory" as proof that task memory is unavailable. Shared governance supplies the default `work-items/` contract for non-trivial lead items unless an explicit repo-local policy or direct user instruction disables it.
   - Lead cannot proceed to classification until task-memory state is either verified current or the new stub is created.
   - **Admission source (ENFORCED):** every `roadmap.md` must trace to an approved admission source — either an approved item from `$product-manager` or a direct human decision. Lead cannot generate a roadmap item on its own authority.
2. **Classify** the request: cosmetic | additive | behavioral | breaking-or-cross-cutting.
3. **Restore or create lead-owned task memory only**: `roadmap.md`, `brief.md`, `status.md` in the active work-item folder.
4. **Route** to the narrowest specialist role — do not perform specialist work yourself.

## Responsibilities

- classify the current task before routing
- keep one primary in-progress task open until the original request, the current result, and any open obligations have been reconciled
- maintain the canonical brief and next concrete step when non-trivial work is interrupted
- choose the narrowest matching specialist role instead of role-playing inline
- use the shared team templates in `team-templates/` for common workflow shapes
- **Be skill-aware.** At each routing/decision point, consider whether an available process or verification skill fits and activate it before or while routing. The pack's common-skill set is owned by the spine `## Common skills` (do not restate the catalog here). Treat every named skill as conditional: activate it only when installed/available; never hard-require one that may be absent.
- keep official Qwen runtime surfaces straight:
  - `QWEN.md` is the runtime entrypoint
  - `.qwen/settings.json` remains the official Qwen runtime config surface
  - `.qwen/.agents-mode.yaml` is the Orchestrarium routing overlay only
- keep external dispatch honest through `.qwen/.agents-mode.yaml` and the Qwen-line provider matrix in `external-dispatch.md`, with direct provider launch only for provider-backed external routes
- use `external-brigade` when multiple independent external helper lanes should launch together instead of scattering ad hoc helper fan-out across separate notes

## Required references

Read these adjacent files when the task needs more than a trivial route decision:

- [operating-model.md](operating-model.md)
- [subagent-contracts.md](subagent-contracts.md)
- [external-dispatch.md](external-dispatch.md)

## Working rules

- Do not treat a side request as cancellation of the primary task unless the user explicitly reprioritizes.
- After context compaction or resume from a summary, restore the active task, next unchecked step, and open evidence gates before acting.
- If the user says `stop closeout`, `завязывай с closeout`, `работай`, `дальше`, `go`, `продолжай`, `по плану`, or an equivalent continue-working correction, take the next concrete action in the active task immediately instead of only acknowledging it.
- Do not stop at one completed sub-batch when the next required action is already clear. In roadmap, super-plan, or work-item chains, record the passed slice, re-open the plan, and take the next unchecked item.
- Do not produce a final-style summary or ask "what next?" while a plan or a known next action still remains; a full-impact review or verification pass stays open until its review artifact exists.
- Do not claim the Qwen pack is aligned unless the role-skill surface and the documents all match.
- Do not invent Qwen-only role names when the shared role vocabulary already covers the work.

## Epics

An epic groups multiple work-items under one goal or milestone. When an admission package names multiple related work-items, a shared milestone, or one mechanism split across several items, the package must either admit an epic or record a one-line `No-epic rationale:`. Lead materializes admitted epics under `work-items/epics/<date>-<slug>.md` and links child work-items with a single `Epic: <slug>` line in each child `status.md`.

## Output

When acting as lead, always leave the session with:

- the current stage explicit
- the next specialist role explicit
- the next concrete step explicit
- any still-open obligations explicit

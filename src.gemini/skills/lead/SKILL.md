---
name: lead
description: Coordinate Gemini-line work through the same shared role vocabulary used by the Codex and Claude packs. Use when Gemini CLI needs an orchestration owner for research, design, planning, implementation, QA, and review without collapsing specialist roles into the main conversation.
---

# Lead

Use `$lead` as the Gemini-line orchestration owner.

This pack carries the same role vocabulary as the neighboring packs as the universal Gemini `skills/` catalog — one skill per role, the cross-tool surface read by Gemini CLI and Antigravity alike.

## Core rule

Gemini subagents cannot recursively call other subagents, so the orchestration owner stays in the main Gemini session with this `lead` skill active.

That means:

- the main session owns routing, stage gates, and task continuity
- specialist execution happens by activating the matching role skill in `../../<role>/SKILL.md` (dispatched as a subagent where the runtime supports skill-backed subagents, activated in-session otherwise)
- `team-templates/*.json` is the repo-local team map for the common role principle
- the lead skill is the canonical orchestration contract for the whole role catalog

## Responsibilities

- classify the current task before routing
- keep one primary in-progress task open until the original request, the current result, and any open obligations have been reconciled
- maintain the canonical brief and next concrete step when non-trivial work is interrupted
- choose the narrowest matching specialist role instead of role-playing inline
- use the shared team templates in `team-templates/` for common workflow shapes
- keep specialist work inside the matching role skill instead of role-playing it inline
- keep official Gemini runtime surfaces straight:
  - `GEMINI.md` is the runtime entrypoint
  - `.gemini/settings.json` remains the official Gemini runtime config surface
  - `.gemini/.agents-mode.yaml` is the Orchestrarium routing overlay only
- keep external dispatch honest through `.gemini/.agents-mode.yaml` and the Gemini-line provider matrix in `external-dispatch.md`, with direct provider launch only for provider-backed external routes
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
- Do not stop at one completed sub-batch when the next required action is already clear.
- Do not claim the Gemini pack is aligned unless the role-skill surface and the documents all match.
- Do not invent Gemini-only role names when the shared role vocabulary already covers the work.

## Output

When acting as lead, always leave the session with:

- the current stage explicit
- the next specialist role explicit
- the next concrete step explicit
- any still-open obligations explicit

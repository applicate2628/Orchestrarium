# Implement

Execute an approved plan from `work-items/active/` phase by phase.

## When to auto-invoke

Apply this command's flow automatically when:

- an accepted plan exists in `work-items/active/<slug>/plan.md` and the user asks to proceed, continue, or execute
- user explicitly says "implement plan X", "execute the plan for Y", "run phase N"
- user says "continue", "next phase", "go ahead" while a work-item is mid-implementation — if the session is FRESH (no in-context chain state), first apply `/agents-resume`'s load-and-validate steps (git-divergence + `Depends-on` checks), then continue
- user references a specific phase by slug or number

The user does not need to type `/agents-implement` for this flow to fire. Apply it transparently and announce the routing decision in your first response.

**Do NOT auto-invoke** for "build feature X" without an accepted plan — that is the `/agents-design` flow's territory first. If the user's request is for a new feature with no prior research/design/plan, route through `agents-design.md` instead.

## Steps

1. **Find the plan.** Check `$ARGUMENTS`:
   - If a slug or path is given, load that work-item
   - If empty, check `work-items/active/` for items with a plan artifact. List them and ask the user to pick one.
   - If no plans found, suggest running `/agents-design` first.

2. **Read the plan.** Load the plan artifact (e.g., `plan.md`) and `status.md`. Identify:
   - Total phases and their order
   - Current phase (from status.md, or phase 1 if fresh)
   - Dependencies between phases
   - Acceptance criteria per phase

3. **Execute phase by phase.** For each phase:
   - **Implementer** (Agent tool, appropriate engineer `subagent_type`, or `external-worker` when external dispatch is preferred): implement the phase within the allowed change surface. Pass the phase spec, acceptance criteria, and any constraints from the plan.
   - **QA** (Agent tool, `subagent_type: qa-engineer`, or `external-reviewer` when external dispatch is preferred): verify the phase — run tests, check acceptance criteria, write bug files if defects found.
   - If QA returns `PASS` — update `status.md`, move to next phase.
   - If QA returns `REVISE` — check the classification:
     - **regression**: loop back to implementer to fix code, then re-run QA
     - **contract-change**: loop back to the **same implementer** to update tests under the new contract (the implementer who changed the behavior owns the test adaptation), then re-run QA
     - **test-rot**: file low-severity bug, continue to next phase
     - Present findings to user — user may override: fix now or defer to registry.
   - If QA returns `BLOCKED` — stop and present the blocker to the user.

4. **Between phases.** Update `status.md` after each phase completion. Ask the user to confirm before starting the next phase.
   - **After parallel phases**: check for semantic conflicts and unintended interactions between the parallel agents' outputs (see parallel execution protocol in `operating-model.md`). Resolve conflicts before advancing.

5. **Completion.** Save final report to `work-items/active/<slug>/implementation-report.md` and log to `.reports/`. When all phases are done:
   - Run architecture reviewer (Agent tool, `subagent_type: architecture-reviewer`) on the full changeset
   - Present summary: phases completed, tests passed, open bugs, residual risk
   - Suggest `/agents-review` for final review before commit
   - **Close the work-item once it is delivered (the user commits/pushes) or parked.** Do not leave a delivered item in `work-items/active/` — apply the Recovery rule's close step in `CLAUDE.md` (write `closure.md`, move the folder to `work-items/archive/<YYYY-MM>/<slug>/`, move its `work-items/index.md` row to Archived). If the session ends before the user commits, the work-items archival Stop-hook flags the still-open item on the next session. If the work-item declares an `Epic:`, also refresh the parent epic's roll-up in `work-items/epics/` and close the epic (`status: closed` + `## Closure`) when this was its last open child and the epic goal is met (see the lead skill `## Epics`).

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Choose the implementer subagent_type based on the phase domain (backend-engineer, frontend-engineer, etc.).
- Follow evidence-based completion: show fresh execution evidence per phase.
- Independent phases (no shared change surface) may be implemented in parallel.
- Never skip QA for any phase.
- **Do NOT commit automatically.** After all phases complete and the final review passes, present the full changeset to the user. The user decides when to commit.

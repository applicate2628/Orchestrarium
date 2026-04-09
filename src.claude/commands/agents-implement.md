# Implement

Execute an approved plan from `work-items/active/` phase by phase.

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
   - **Implementer** (Agent tool, appropriate engineer `subagent_type`): implement the phase within the allowed change surface. Pass the phase spec, acceptance criteria, and any constraints from the plan.
   - **QA** (Agent tool, `subagent_type: qa-engineer`): verify the phase — run tests, check acceptance criteria, write bug files if defects found.
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

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Choose the implementer subagent_type based on the phase domain (backend-engineer, frontend-engineer, etc.).
- Follow evidence-based completion: show fresh execution evidence per phase.
- Independent phases (no shared change surface) may be implemented in parallel.
- Never skip QA for any phase.
- **Do NOT commit automatically.** After all phases complete and the final review passes, present the full changeset to the user. The user decides when to commit.

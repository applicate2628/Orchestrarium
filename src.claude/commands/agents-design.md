# Design

Run the full research-to-plan chain using the `research` template.

## Steps

1. **Get the task.** Use `$ARGUMENTS` as the feature or change description. If empty, ask the user what to design.

2. **Run the full research chain.** Follow the `research` template from CLAUDE.md:
   - **Analyst** (`subagent_type: analyst`): investigate the codebase — locate relevant files, existing patterns, contracts, and constraints. Return a research memo.
   - **Architect** (`subagent_type: architect`): produce a design from the research — architecture decisions, API contracts, data model changes, tradeoffs, and test strategy.
   - **Planner** (`subagent_type: planner`): break the accepted design into small independent delivery phases with file scope, dependencies, acceptance criteria, and quality gates.

3. **Handle REVISE at each stage:**
   - If **architect** returns `REVISE` on the research → route gaps back to analyst → re-run architect. Max 3 iterations.
   - If **planner** returns `REVISE` on the design → route gaps back to architect → re-run planner. Max 3 iterations.
   - If any stage exceeds the iteration cap, present findings and remaining gaps to the user.

4. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - Create `work-items/active/<date>-<slug>/` with `research.md`, `design.md`, `plan.md`, `status.md`
   - Log plan to `.plans/YYYY-MM/plan(<role>)-YYYY-MM-DD_HH-MM_topic.md`

5. **Report.** Present:
   - Design summary (key decisions, tradeoffs)
   - Implementation plan (phases, files, acceptance criteria)
   - Ask if the user wants to proceed with implementation

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Pass accepted artifacts between stages: research → architect, design → planner.
- This is read-only — do not modify any files.
- Save the plan to `work-items/active/` if the user approves, following the recovery rule.

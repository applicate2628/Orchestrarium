# Design

Run the full research-to-plan chain using the `research` template.

## Steps

1. **Get the task.** Use `$ARGUMENTS` as the feature or change description. If empty, ask the user what to design.

2. **Run the full research chain.** Follow the `research` template from CLAUDE.md:
   - **Analyst** (`subagent_type: analyst`): investigate the codebase — locate relevant files, existing patterns, contracts, and constraints. Return a research memo.
   - **Architect** (`subagent_type: architect`): produce a design from the research — architecture decisions, API contracts, data model changes, tradeoffs, and test strategy.
   - **Planner** (`subagent_type: planner`): break the accepted design into small independent delivery phases with file scope, dependencies, acceptance criteria, and quality gates.

3. **Report.** Present:
   - Design summary (key decisions, tradeoffs)
   - Implementation plan (phases, files, acceptance criteria)
   - Ask if the user wants to proceed with implementation

## Rules

- Pass accepted artifacts between stages: research → architect, design → planner.
- This is read-only — do not modify any files.
- Save the plan to `work-items/active/` if the user approves, following the recovery rule.

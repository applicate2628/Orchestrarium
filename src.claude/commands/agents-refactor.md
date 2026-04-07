# Refactor

Run a safe refactoring chain with blast-radius analysis and verification.

## Steps

1. **Get the scope.** Use `$ARGUMENTS` as the refactoring description. If empty, ask the user what to refactor and why.

2. **Analyze blast radius.** Invoke **Analyst** (Agent tool, `subagent_type: analyst`):
   - Map the change surface: which files, modules, contracts are affected
   - Identify callers, dependents, and must-not-break surfaces
   - Assess risk: is this a local rename or a cross-module restructuring?

3. **Verify architecture fit.** Invoke **Architect** (Agent tool, `subagent_type: architect`):
   - Review the analyst's findings
   - Confirm the refactoring improves or preserves architecture quality
   - Define constraints: what must not change in behavior, what contracts must hold
   - If blast radius is too wide, recommend splitting into phases

4. **Plan.** If the architect recommends phases, invoke **Planner** (Agent tool, `subagent_type: planner`):
   - Break into small independent phases with file scope and acceptance criteria
   - Save plan to `work-items/active/` and suggest `/agents-implement`

5. **Execute.** If single-phase (or user wants immediate execution):
   - **Implementer** (Agent tool, appropriate engineer `subagent_type`): apply the refactoring within the architect's constraints
   - **QA** (Agent tool, `subagent_type: qa-engineer`): verify no regressions — all existing tests pass, behavior preserved
   - **Architecture reviewer** (Agent tool, `subagent_type: architecture-reviewer`): confirm the result improves readability, maintainability, and fits the architecture

6. **Handle reviewer verdict:**
   - If architecture reviewer returns `PASS` → proceed to report
   - If architecture reviewer returns `REVISE` → route to the correct target (see architecture-reviewer REVISE routing: code issues → implementer, design issues → architect, plan issues → planner) → re-run QA → re-run architecture reviewer. Max 3 iterations, then escalate to user.
   - If architecture reviewer returns `BLOCKED` → present to user with classification

7. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - Log to `.reports/YYYY-MM/report(<role>)-YYYY-MM-DD_HH-MM_topic.md`

8. **Report.** Present:
   - What was refactored and why
   - Blast radius (files touched, contracts affected)
   - Behavior preserved vs changed (must be explicit per logic-revision discipline)
   - Test results
   - Architecture reviewer verdict

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Refactoring MUST NOT change behavior unless explicitly stated and approved by the user.
- Follow logic-revision discipline: state what is preserved, what changes, what callers are affected.
- **Save recovery state** between stages in `work-items/active/<date>-<slug>/` per the recovery rule in CLAUDE.md: `status.md` + the accepted artifact from each completed stage.
- If blast radius exceeds 5 files, strongly recommend planning into phases first.
- **Do NOT commit automatically.** Present the refactoring with test evidence. The user decides when to commit — suggest `/agents-review` first.

# Bug Fix

Run a bugfix chain using the `quick-fix` template.

## Steps

1. **Get the bug description.** Use `$ARGUMENTS` as the bug description. If empty, ask the user to describe the bug.

2. **Run the quick-fix chain.** Follow the `quick-fix` template from CLAUDE.md:
   - **Analyst** (`subagent_type: analyst`): locate the bug — find the relevant files, root cause, and affected surfaces
   - **Implementer** (appropriate engineer subagent): fix the bug with minimal scope — follow bug-fix scope and change-surface minimization from Engineering hygiene
   - **QA** (`subagent_type: qa-engineer`): verify the fix — check the intended fix works and no regressions were introduced

3. **Report.** Present:
   - Root cause
   - What was changed (file, line, before/after)
   - Evidence the fix works (test output, verification)
   - Any residual risk

## Rules

- Keep the fix narrowly scoped — no unrelated refactors.
- Choose the implementer based on what area the bug is in (backend-engineer, frontend-engineer, etc.).
- Follow evidence-based completion: show fresh execution evidence before claiming done.

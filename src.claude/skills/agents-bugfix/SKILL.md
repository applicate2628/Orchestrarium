---
name: agents-bugfix
description: Classify the bug severity and run the appropriate template chain.
disable-model-invocation: true
---
# Bug Fix

Classify the bug severity and run the appropriate template chain.

## Steps

1. **Get the bug description.** Use `$ARGUMENTS` as the bug description. If empty, check `work-items/bugs/` for files with `status: open`. If open bugs exist, list them (filename, severity, first line of Description) and ask the user to pick one or describe a new bug. If no open bugs and no arguments, ask the user to describe the bug.

2. **Triage — classify the bug.** Invoke **Analyst** (`subagent_type: analyst`) to investigate: locate the root cause, affected files, and blast radius. The analyst's report must recommend a template:

   | Analyst finding | Template | Chain |
   | --- | --- | --- |
   | Single file/module, cause clear | `quick-fix` | implementer → QA |
   | Multiple modules, unclear cause, regression | `full-delivery` | architect → planner → implementer → QA → architecture-reviewer |
   | Auth, credentials, trust boundary involved | `security-sensitive` | security-engineer → implementer → QA → security-reviewer |
   | SLA breach, perf degradation | `performance-sensitive` | performance-engineer → implementer → QA → performance-reviewer |
   | Multiple risk domains | `combined-critical` | lead coordinates all risk owners |

3. **Confirm template with user.** Present the analyst's recommendation and ask the user to confirm or override. For `requiresLead: true` templates, invoke `$lead` to coordinate.

4. **Run the chain.** Execute the selected template. Each stage via Agent tool with appropriate `subagent_type`.

5. **Handle QA verdict:**
   - `PASS` → proceed to report
   - `REVISE` with **regression** bugs → loop back to implementer to fix code, then re-run QA
   - `REVISE` with **contract-change** test failures → loop back to the **same implementer** to update tests under the new contract, then re-run QA
   - `BLOCKED` → stop and present to user

6. **Handle reviewer verdict** (for templates with reviewer stages — `full-delivery`, `security-sensitive`, `performance-sensitive`):
   - If reviewer returns `PASS` → proceed to report
   - If reviewer returns `REVISE` → route findings to the appropriate role (see architecture-reviewer REVISE routing for target). Re-run QA after fixes, then re-run reviewer. Max 3 iterations, then escalate to user.
   - If reviewer returns `BLOCKED` → present to user with classification (`BLOCKED:dependency` or `BLOCKED:prerequisite`)

7. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If bug came from registry → update `work-items/bugs/<file>` status
   - Log fix report to `.reports/YYYY-MM/report(<role>)-YYYY-MM-DD_HH-MM_topic.md`

8. **Report.** Present:
   - Root cause
   - Template used and why
   - What was changed (file, line, before/after)
   - Evidence the fix works (test output, verification)
   - Any residual risk

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Keep the fix narrowly scoped — no unrelated refactors.
- Choose the implementer based on what area the bug is in (backend-engineer, frontend-engineer, etc.).
- Follow evidence-based completion: show fresh execution evidence before claiming done.
- **Do NOT commit after fixing.** Present the fix to the user with evidence. The user decides when to commit — only after they are satisfied with testing and fix reliability. Suggest running `/agents-test` or `/agents-review` before committing.
- When fixing a bug from the registry, update its file: set `status: fixed` only after QA confirms the fix AND the user approves. If QA says REVISE, keep `status: open`.

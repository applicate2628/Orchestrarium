---
name: agents-bugfix
description: Classify the bug severity and run the appropriate template chain.
disable-model-invocation: true
---
# Bug Fix

Classify the bug severity and run the appropriate template chain.

## When to auto-invoke

Apply this command's flow automatically when the user's request matches any of:

- explicit bug report: "fix this bug", "не работает", "crashes", "broken", error trace or stack pasted
- defective behavior named without a proposed fix: "X is producing wrong output", "Y returns empty when it shouldn't"
- regression flagged: "this used to work", "this broke after change Z"
- bug filename reference: user mentions a `work-items/bugs/<file>` slug

The user does not need to type `/agents-bugfix` for this flow to fire. Apply it transparently, announce the routing decision in your first response ("I'm routing this through the bugfix flow because..."), and let the user redirect if the auto-routing was wrong. If the bug's cause is not obvious from the description, load common-skill `$bug-hunting` before the analyst triage in Step 2; if the superpowers plugin is also installed, additionally invoke `Skill: superpowers:systematic-debugging` for the broader diagnostic methodology. The `$bug-hunting` common-skill is shipped by this pack and always available; `superpowers:systematic-debugging` is an external plugin and may not be present in every install.

## Steps

1. **Get the bug description.** Use `$ARGUMENTS` as the bug description. If empty, check `work-items/bugs/` for files with `status: open`. If open bugs exist, list them (filename, severity, first line of Description) and ask the user to pick one or describe a new bug. If no open bugs and no arguments, ask the user to describe the bug.

2. **Triage — classify the bug.** Invoke **Analyst** (`subagent_type: analyst`) to investigate: locate the root cause, affected files, and blast radius. The analyst's report must recommend a template:

   | Analyst finding | Template | Chain |
   | --- | --- | --- |
   | Single file/module, cause clear | `quick-fix` | implementer or external-worker → QA or external-reviewer |
   | Multiple modules, unclear cause, regression | `full-delivery` | architect → planner → implementer or external-worker → QA or external-reviewer → architecture-reviewer or external-reviewer |
   | Auth, credentials, trust boundary involved | `security-sensitive` | security-engineer → implementer or external-worker → QA or external-reviewer → security-reviewer |
   | SLA breach, perf degradation | `performance-sensitive` | performance-engineer → implementer or external-worker → QA or external-reviewer → performance-reviewer |
   | Multiple risk domains | `combined-critical` | main conv (as Lead) coordinates all risk owners |

3. **Confirm template with user.** Present the analyst's recommendation and ask the user to confirm or override. For `requiresLead: true` templates, hold the Lead role in the main conversation (activate the `/lead` skill) and run the lead pipeline to coordinate — do not spawn `$lead`.

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
- When routing preferences favor external dispatch, `external-worker` may replace the chosen implementer and `external-reviewer` may replace the QA/review-side slot. Mandatory security and performance reviewers remain internal in their sensitive templates.
- Follow evidence-based completion: show fresh execution evidence before claiming done.
- **Do NOT commit after fixing.** Present the fix to the user with evidence. The user decides when to commit — only after they are satisfied with testing and fix reliability. Suggest running `/agents-test` or `/agents-review` before committing.
- When fixing a bug from the registry, update its file: set `status: fixed` only after QA confirms the fix AND the user approves. If QA says REVISE, keep `status: open`. Two other terminal states exist for bugs that are not fixed: `wontfix` (the bug is acknowledged but deliberately not fixed — keep a one-line reason) and `duplicate` (the bug restates an existing one — name the surviving bug id). The canonical bug status enum (`open | fixed | wontfix | duplicate`) and its transition rules are defined once in `qa-engineer.md`'s bug status lifecycle; this command follows that enum, it does not redefine it. The `/agents-status` open-scan still lists only `status: open`.
- **Second-cross-break stop:** If a second fix in the same session breaks a previously working neighbor, STOP all edits. Before any further edit, run a read-only multi-angle structural diagnosis covering (1) the owning invariant and call/data flow, (2) sibling modes/surfaces, and (3) timing/lifecycle/shared-state interactions; identify which prior edit changed the real symptom and verify the structural cause.

# Performance Fix

Fix a performance issue using the `performance-sensitive` template.

## Steps

1. **Get the issue.** Check `$ARGUMENTS`:
   - If a description or file path is given, use that
   - If empty, check `work-items/performance/` for files with `status: open`. If open issues exist, list them (severity, filename, metric, budget vs actual) and ask the user to pick one or describe a new issue.
   - If no open issues and no arguments, ask the user to describe the performance problem.

2. **Analyze.** Invoke **Performance engineer** (Agent tool, `subagent_type: performance-engineer`):
   - Profile or model the bottleneck
   - Confirm the metric, budget, and actual values
   - Recommend optimization strategy and constraints
   - If the issue is architectural, recommend escalation to `full-delivery`

3. **Implement.** Invoke **Implementer** (Agent tool, appropriate engineer `subagent_type`, or `external-worker` when external dispatch is preferred):
   - Apply the optimization within the performance engineer's constraints. When external dispatch is preferred, the implementer may be `external-worker`.
   - Measure before/after

4. **Verify.** Invoke **QA** (Agent tool, `subagent_type: qa-engineer`, or `external-reviewer` when external dispatch is preferred):
   - Verify no functional regressions. When external dispatch is preferred, the QA slot may be `external-reviewer`.

5. **Performance review.** Invoke **Performance reviewer** (Agent tool, `subagent_type: performance-reviewer`):
   - Verify the optimization meets the budget
   - Check methodology and residual risk

6. **Handle reviewer verdict:**
   - If performance reviewer returns `PASS` → proceed to report
   - If performance reviewer returns `REVISE` → route findings back to implementer → re-run QA → re-run performance reviewer. Max 3 iterations (see REVISE iteration cap in `operating-model.md`), then escalate to user.
   - If performance reviewer returns `BLOCKED` → present to user with classification (`BLOCKED:dependency` or `BLOCKED:prerequisite`)

7. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If issue from registry → update `work-items/performance/<file>` status
   - Log to `.reports/YYYY-MM/report(<role>)-YYYY-MM-DD_HH-MM_topic.md`

8. **Report.** Present:
   - Bottleneck identified and root cause
   - Optimization applied (file, line, before/after)
   - Metric: before → after (budget: target)
   - QA and performance review verdicts
   - Any residual risk

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- When fixing an issue from the registry, update its file: set `status: fixed` after performance reviewer confirms. If reviewer says REVISE, keep `status: open`.
- **Save recovery state** between stages in `work-items/active/<date>-<slug>/` per the recovery rule in CLAUDE.md: `status.md` + the accepted artifact from each completed stage.
- Follow evidence-based completion: show measured results, not estimates.
- Confirm the bottleneck before optimizing — do not guess.
- **Do NOT commit after fixing.** Present the optimization with measured evidence. The user decides when to commit — only after they are satisfied with reliability. Suggest running `/agents-test` before committing.

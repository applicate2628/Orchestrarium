# Performance Fix

Fix a performance issue using the `performance-sensitive` template.

## When to auto-invoke

Apply this command's flow automatically when the user's request matches any of:

- performance budget or SLA breach: "this endpoint is over the latency budget", "we're missing the SLA", "the p99 regressed"
- explicit slowness with a target or constraint: "reduce p99 below 200ms", "this query takes 30s, the budget is 1s", "startup must fit in 2 seconds"
- throughput or resource pressure tied to a metric: "throughput dropped", "memory keeps climbing", "CPU is pegged under load"
- performance issue filename reference: user mentions a `work-items/performance/<file>` slug

The user does not need to type `/agents-perf` for this flow to fire. Apply it transparently, announce the routing decision in your first response ("I'm routing this through the performance flow because the report names a measurable budget/SLA breach"), and let the user redirect if the auto-routing was wrong.

**Do NOT auto-invoke** for a functional defect with no performance dimension — that is `/agents-bugfix` territory even if the symptom looks like a hang. When a bug report names both wrong behavior and a budget/SLA breach, this performance flow takes precedence over `/agents-bugfix` per the "pick the most specialized one" resolution rule in CLAUDE.md. Confirm the bottleneck before optimizing; do not auto-route a metric-free slowness report ("feels slow", "X is too slow", "speed up Y") — ask for a measurable target first, then enter this flow.

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
   - If performance reviewer returns `REVISE` → route findings back to implementer → re-run QA → re-run performance reviewer under the shared spine's consecutive same-role/same-artifact `REVISE`-cycle cap, then escalate to the user when exhausted.
   - If performance reviewer returns `BLOCKED` → present to user with classification (`BLOCKED:dependency` or `BLOCKED:prerequisite`)

7. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If issue from registry → update `work-items/performance/<file>` status
   - With an active `work-items/active/<slug>/`, write only its canonical artifact and return concise result/provenance for the root ledger. With no active item, a meaningful standalone result MAY use one `.reports/` summary.

8. **Report.** Present:
   - Bottleneck identified and root cause
   - Optimization applied (file, line, before/after)
   - Metric: before → after (budget: target)
   - QA and performance review verdicts
   - Any residual risk

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- When fixing an issue from the registry, update its file (the status enum `open | fixed | wontfix` is owned by `$performance-engineer`): set `status: fixed` only after the performance reviewer confirms AND the user approves; `wontfix` records an accepted-tradeoff reason. If the reviewer says REVISE, keep `status: open`.
- **Save recovery state** between stages in `work-items/active/<date>-<slug>/` per the recovery rule in CLAUDE.md: `status.md` + the accepted artifact from each completed stage.
- Follow evidence-based completion: show measured results, not estimates.
- Confirm the bottleneck before optimizing — do not guess.
- **Do NOT commit after fixing.** Present the optimization with measured evidence. The user decides when to commit — only after they are satisfied with reliability. Suggest running `/agents-test` before committing.

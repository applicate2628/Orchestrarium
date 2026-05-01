# Code Review

Run a full read-only repository impact review starting from current changes or a specified review target. Changed files are only the entry point; the review must cover the wider affected surface, including unchanged dependents, contracts, tests, config, and nearby logic.

## Steps

1. **Determine scope.** Check `$ARGUMENTS`:
   - If a PR number, branch, commit range, or other review target is given, use that
   - Otherwise, review unstaged/staged changes (`git diff` + `git diff --cached`)
   - If no changes found, tell the user and stop
   - If the user mentions a bug, review thread, accepted plan, or expected fix list, use that as the completion baseline

2. **Run the review chain.** Follow the `review` template from CLAUDE.md:
   - **Analyst** (`subagent_type: analyst`): investigate what changed, which contracts or behaviors moved, which unchanged callers or dependents are affected, and where logic may now be incomplete
   - Require the analyst to inspect changed code plus unchanged callers, dependents, tests, config, schemas, and adjacent modules that may now be inconsistent
   - **QA / review-side adapter** (`subagent_type: qa-engineer`, or `external-reviewer` when external dispatch is preferred for an eligible QA-side slot): verify regression risk, edge cases, validation sufficiency, and whether untouched behavior is now inconsistent with the new logic
   - **Reviewer lane**: always run **Architecture reviewer** (`subagent_type: architecture-reviewer`, or `external-reviewer` when the slot is eligible and policy allows it)
   - Add **Security reviewer** (`subagent_type: security-reviewer`) if the change touches auth, trust boundaries, secrets, dangerous config, input validation, or vulnerability surfaces
   - Add **Performance reviewer** (`subagent_type: performance-reviewer`) if the change touches hot paths, query plans, rendering loops, budgets, throughput, or latency-sensitive behavior
   - Add **UX / accessibility / UI test reviewers** (`subagent_type: ux-reviewer`, `accessibility-reviewer`, or `ui-test-engineer`) when the affected surface is user-facing and the risk is interaction quality rather than pure logic

3. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/review.md`
   - Log to `.reports/YYYY-MM/report(<role>)-YYYY-MM-DD_HH-MM_topic.md`

4. **Compile results.** Present a unified review with:
   - Scope reviewed
   - Issues found (CRITICAL / HIGH / MEDIUM / LOW)
   - Impacted unchanged surfaces that were checked
   - What could not be verified
   - Recommendations
   - Verdict: PASS / REVISE / BLOCKED

If the user asked "did we fix everything?", answer that directly before the detailed findings.

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Independent stages may be launched in parallel. Sequential stages must wait for the previous agent's artifact.
- Pass accepted artifacts between stages — analyst findings go to QA, both go to reviewer.
- If any stage finds a CRITICAL issue, flag it immediately without waiting for later stages.
- Treat changed files as entry points, not the review boundary.
- Do not modify any files — this is read-only.

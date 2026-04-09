# Code Review

Run a review chain on current changes using the `review` template.

## Steps

1. **Determine scope.** Check `$ARGUMENTS`:
   - If a PR number or branch is given, use that
   - Otherwise, review unstaged/staged changes (`git diff` + `git diff --cached`)
   - If no changes found, tell the user and stop

2. **Run the review chain.** Follow the `review` template from CLAUDE.md:
   - **Analyst** (`subagent_type: analyst`): investigate the changes — what was modified, why, what contracts are affected
   - **QA / review-side adapter** (`subagent_type: qa-engineer`, or `external-reviewer` when external dispatch is preferred): verify test coverage, edge cases, regression risk
   - **Architecture reviewer** (`subagent_type: architecture-reviewer`, or `external-reviewer` when the slot is eligible): check fit with existing architecture, readability, maintainability

3. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/review.md`
   - Log to `.reports/YYYY-MM/report(<role>)-YYYY-MM-DD_HH-MM_topic.md`

4. **Compile results.** Present a unified review with:
   - Summary of changes
   - Issues found (CRITICAL / HIGH / MEDIUM / LOW)
   - Recommendations
   - Verdict: PASS / REVISE / BLOCKED

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Independent stages may be launched in parallel. Sequential stages must wait for the previous agent's artifact.
- Pass accepted artifacts between stages — analyst findings go to QA, both go to reviewer.
- If any stage finds a CRITICAL issue, flag it immediately without waiting for later stages.
- Do not modify any files — this is read-only.

# Test

Write or verify tests for specified code using the QA agent.

## Steps

1. **Determine scope.** Check `$ARGUMENTS`:
   - If a file or function name is given, focus on that
   - If "coverage" is mentioned, run coverage analysis
   - If empty, analyze recent changes (`git diff`) and test those

2. **Read project policies.** Check `## Project policies` in CLAUDE.md for testing methodology and coverage target.

3. **Run QA.** Invoke `subagent_type: qa-engineer`:
   - Analyze the target code for testable behavior
   - Write or update tests following the configured testing methodology (TDD, test-after, etc.)
   - Run tests and report results
   - If a coverage target is configured, check coverage meets the target

4. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/test-report.md`
   - Log to `.reports/YYYY-MM/report(qa-engineer)-YYYY-MM-DD_HH-MM_topic.md`

5. **Report.** Present:
   - Tests written or updated (file paths)
   - Test results (pass/fail count)
   - Coverage if applicable
   - Any untestable areas or gaps

## Rules

- **The QA stage MUST be invoked via the Agent tool** with `subagent_type: qa-engineer`. Do not role-play QA inline.
- Follow the project's testing methodology from policies.
- Match existing test patterns and frameworks in the repo.
- Do not change source code — only test files.
- When tests reveal defects, the QA agent must create bug files in `work-items/bugs/` following the bug registry format from the qa-engineer role. This ensures defects survive across sessions even if not fixed immediately.

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

4. **Report.** Present:
   - Tests written or updated (file paths)
   - Test results (pass/fail count)
   - Coverage if applicable
   - Any untestable areas or gaps

## Rules

- Follow the project's testing methodology from policies.
- Match existing test patterns and frameworks in the repo.
- Do not change source code — only test files.

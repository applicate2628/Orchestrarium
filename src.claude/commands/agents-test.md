# Test

Write or verify tests for specified code using the QA agent.

## When to auto-invoke

Apply this command's flow automatically when the user's request matches any of:

- explicit test-writing request: "add tests for X", "write unit tests for Y", "cover Z with tests"
- coverage question or request: "what's the coverage of Y?", "improve coverage for module W", "are there tests for this?"
- verify-existing-tests intent: "do the tests pass for X?", "check that Y is tested", "run and verify the tests on Z"

The user does not need to type `/agents-test` for this flow to fire. Apply it transparently, announce the routing decision in your first response ("I'm routing this through the test flow because you asked to add/verify tests or check coverage"), and let the user redirect if the auto-routing was wrong.

**Do NOT auto-invoke** for a steered, multi-round interactive testing session where the user wants to drive scenario by scenario — that is `/agents-qa-session` territory; this flow is the one-shot "write or verify tests for this scope" task. Do not auto-route a confirmed defect here — fixing belongs to `/agents-bugfix`; this flow only writes/verifies tests and files bug records for any defects it surfaces.

## Steps

1. **Determine scope.** Check `$ARGUMENTS`:
   - If a file or function name is given, focus on that
   - If "coverage" is mentioned, run coverage analysis
   - If empty, analyze recent changes (`git diff`) and test those

2. **Read project policies.** Check `## Project policies` in CLAUDE.md for testing methodology and coverage target.

3. **Run QA.** Invoke `subagent_type: qa-engineer` or `external-reviewer` when the routing contract prefers external dispatch:
   - Analyze the target code for testable behavior
   - Write or update tests following the configured testing methodology (TDD, test-after, etc.)
   - Run tests and report results
   - If a coverage target is configured, check coverage meets the target
   - When external dispatch is preferred, use `external-reviewer` for this QA slot instead of `qa-engineer`

4. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/test-report.md`
   - Log to `.reports/YYYY-MM/report(<actual-role>)-YYYY-MM-DD_HH-MM_topic.md`

5. **Report.** Present:
   - Tests written or updated (file paths)
   - Test results (pass/fail count)
   - Coverage if applicable
   - Any untestable areas or gaps

## Rules

- **The QA stage MUST be invoked via the Agent tool** with `subagent_type: qa-engineer` or `external-reviewer` when the routing contract prefers external dispatch. Do not role-play QA inline.
- Follow the project's testing methodology from policies.
- Match existing test patterns and frameworks in the repo.
- Do not change source code — only test files.
- When tests reveal defects, the QA agent must create bug files in `work-items/bugs/` following the bug registry format from the qa-engineer role. This ensures defects survive across sessions even if not fixed immediately.

---
name: agents-qa-session
description: Interactive testing session — you direct, one QA agent investigates and documents.
disable-model-invocation: true
---
# QA Session

Interactive testing session — you direct, one QA agent investigates and documents.

## Steps

1. **Start session.** Check `$ARGUMENTS`:
   - If a scope is given (file, module, feature), start there
   - If empty, ask the user what area to test

2. **Launch QA agent.** Invoke **one** QA agent (Agent tool, `subagent_type: qa-engineer`) with the initial scope and instruction: "This is an interactive QA session. Investigate the given area, report findings, and wait for further direction."

3. **Enter the loop.** Repeat until the user says "done" or "enough":

   a. **Wait for direction.** The user gives a hint, area, scenario, or suspicion. Examples:
      - "check edge cases in the auth module"
      - "what happens with empty input?"
      - "I think the caching is broken when..."
      - "look at error handling in X"

   b. **Forward to QA.** Use `SendMessage` to pass the user's direction to the running QA agent. The agent:
      - Reads the relevant code
      - Identifies testable scenarios based on the hint
      - Runs existing tests if available
      - Writes new test cases for suspicious areas
      - Creates bug files in `work-items/bugs/` for confirmed defects
      - Reports findings

   c. **Present findings.** Show the user:
      - What was tested and how
      - Issues found (with severity)
      - Tests written or proposed
      - Bugs filed: `<filename> — <description>`

   d. **User decides next step:**
      - New direction → go to (a)
      - "fix this" → suggest `/agents-bugfix <bug-slug>`
      - "done" → exit loop

4. **Session summary.** When the user ends the session, present:
   - Total areas explored
   - Bugs filed (with links to bug files)
   - Tests written (file paths)
   - Areas not covered / suggestions for next session

## Rules

- **Launch one QA agent** via Agent tool at the start. Continue the session via `SendMessage` — do not spawn a new agent per round.
- The QA agent keeps full context of the session across rounds — no need to repeat findings.
- Do NOT commit any code. Tests are written but committing is the user's decision.
- Keep each investigation focused — one direction per round, not "test everything".
- The user is in control of pace and direction. Never auto-advance to the next area.

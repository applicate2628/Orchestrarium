# QA Session

Interactive testing session — you direct, one QA agent investigates and documents.

## When to auto-invoke

Apply this command's flow automatically when the user's request matches any of:

- explicit interactive testing intent: "let's test X together", "let's QA this", "I want to poke at Y with you"
- iterative, user-directed exploration: "let's go through the edge cases one by one", "I'll feed you scenarios as we go", "walk through Z with me and we'll probe it"
- a multi-round investigation the user wants to steer (give a hint → see findings → give the next hint), rather than a one-shot task

The user does not need to type `/agents-qa-session` for this flow to fire. Apply it transparently, announce the routing decision in your first response ("I'm routing this through the interactive QA session flow because you want to steer the testing round by round"), and let the user redirect if the auto-routing was wrong.

**Do NOT auto-invoke** for a one-shot "write/verify tests for X" request — that is `/agents-test` territory; this flow is for a steered, multi-round session where the user controls pace and direction. Do not auto-route confirmed bug reports here either — those go to `/agents-bugfix`. The user is in control of the loop; never auto-advance to the next area.

## Steps

1. **Start session.** Check `$ARGUMENTS`:
   - If a scope is given (file, module, feature), start there
   - If empty, ask the user what area to test

2. **Launch QA agent.** Invoke **one** QA agent (Agent tool, `subagent_type: qa-engineer`, or `external-reviewer` when external dispatch is preferred) with the initial scope and instruction: "This is an interactive QA session. Investigate the given area, report findings, and wait for further direction."

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

- **The QA agent MUST be invoked via the Agent tool** (`subagent_type: qa-engineer`, or `external-reviewer` when external dispatch is preferred) at the start. Continue the session via `SendMessage` — do not spawn a new agent per round, and do not role-play the QA agent inline.
- The QA agent keeps full context of the session across rounds — no need to repeat findings.
- Do NOT commit any code. Tests are written but committing is the user's decision.
- Keep each investigation focused — one direction per round, not "test everything".
- The user is in control of pace and direction. Never auto-advance to the next area.

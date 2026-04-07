# Initialize Project Policies

You are guiding the user through project policy configuration for the Claudestrator skill-pack.

## Steps

1. **Read current state.** Read `.claude/CLAUDE.md` and check if a `## Project policies` section already exists.
   - If it exists, show the current policies and ask: "Project policies are already configured. Do you want to review and update them, or start fresh?"
   - If not, proceed to step 2.

2. **Read the catalog.** Read `.claude/policies/catalog.md` to get all available policy areas with their options.

3. **Present policies in groups.** Walk through each policy area one at a time. For each:
   - State the policy name and question
   - List options with brief descriptions
   - Show the default
   - Ask the user to pick (or accept default)
   - If the user says "defaults for the rest" or similar, apply defaults to all remaining policies

4. **Confirm choices.** After all areas are covered, present a summary table of all chosen policies and ask for confirmation.

5. **Write to CLAUDE.md.** Add or replace the `## Project policies` section in `.claude/CLAUDE.md`. Place it between `## Engineering hygiene` and `## Publication safety`. Use this format:

```markdown
## Project policies

- **Testing:** {methodology}, {coverage target or "no coverage target"}
- **Commits:** {format description}
- **Branching:** {model description}
- **File size:** {policy description}
- **Error handling:** {style description}
- **PR review:** {policy description}
- **Documentation:** {when to write}
- **Language style:** {preferences or "follow existing conventions"}
- **Dependencies:** {policy description}
```

6. **Confirm completion.** Tell the user the policies are saved and all agents will follow them. Mention `/agents-policies` to view or update later.

## Rules

- Be concise in explanations — the catalog has the details.
- Accept shorthand answers ("tdd", "80", "conventional", "trunk", etc.).
- If the user gives a custom answer that doesn't match an option, record it as-is.
- Do not add policies that the user explicitly skips.
- Do not change any other section of CLAUDE.md.

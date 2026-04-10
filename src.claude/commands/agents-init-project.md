# Initialize Project Policies

You are guiding the user through project policy configuration for the Claude Code pack.

## Continuity contract

- Use one primary in-progress task at a time.
- Side requests may temporarily interrupt that task, but they do not replace it unless the user explicitly reprioritizes, cancels, or parks it.
- After any side request, explicitly resume the primary task and state the next concrete step.
- After an accepted phase or completed batch, continue to the next clear step unless a real gate blocks progression.
- Before claiming completion, reconcile the current result against the original request and any still-open required follow-up inside the same task.
- If a required next action is already known and still inside the current task, keep the task open instead of stopping at a partial batch.

## Steps

1. **Read current state.**
   - Read `.claude/CLAUDE.md` and check if a `## Project policies` section already exists.
   - Read `.claude/.agents-mode` first; if it is missing, read legacy `.claude/.consultant-mode` only as migration input.
   - If either surface already exists, show the current values and ask whether to keep them, review them, or start fresh.

2. **Read the installed canonical sources.**
   - Read `.claude/agents/contracts/policies-catalog.md`.
   - Read `.claude/agents/contracts/external-dispatch.md`.
   - Use those two files as the canonical source for policy choices, allowed `agents-mode` values, and write rules instead of inventing Claude-line semantics inline.

3. **Present policies in groups.** Walk through each policy area one at a time. For each:
   - State the policy name and question
   - List options with brief descriptions
   - Show the default
   - Ask the user to pick (or accept default)
   - If the user says "defaults for the rest" or similar, apply defaults to all remaining policies

4. **Configure operator modes.**
   - Walk through the canonical Claude-line `agents-mode` keys one at a time:
     - `consultantMode`
     - `delegationMode`
     - `mcpMode`
     - `preferExternalWorker`
     - `preferExternalReviewer`
     - `externalProvider`
   - Use the existing value when present; otherwise default to:
     - `consultantMode: disabled`
     - `delegationMode: manual`
     - `mcpMode: auto`
     - `preferExternalWorker: false`
     - `preferExternalReviewer: false`
     - `externalProvider: auto`
   - Accept shorthand answers such as `force`, `external reviewer only`, or `defaults for the rest`.

5. **Confirm choices.**
   - Present one summary table for `## Project policies`.
   - Present one summary table for `.claude/.agents-mode`.
   - Ask for confirmation before writing.

6. **Write `.claude/.agents-mode`.**
   - Write the canonical file to `.claude/.agents-mode`.
   - Preserve unknown keys when updating an existing file.
   - If only legacy `.claude/.consultant-mode` exists, use it as migration input but write the canonical file to `.claude/.agents-mode`.
   - Keep one key per line and include the inline allowed-values comment for every canonical key.
   - Do not create a new legacy `.claude/.consultant-mode` file.

   Use this canonical shape:

   ```yaml
   consultantMode: {value}  # allowed: external | auto | internal | disabled
   delegationMode: {value}  # allowed: manual | auto | force
   mcpMode: {value}  # allowed: auto | force
   preferExternalWorker: {value}  # allowed: false | true
   preferExternalReviewer: {value}  # allowed: false | true
   externalProvider: {value}  # allowed here: auto | codex | gemini
   ```

7. **Write to CLAUDE.md.** Add or replace the `## Project policies` section in `.claude/CLAUDE.md`. Place it between `## Engineering hygiene` and `## Publication safety`. Use this format:

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

8. **Confirm completion.**
   - Tell the user the policies and operator mode file are saved.
   - Mention `/agents-policies` to view project policies later.
   - Mention `.claude/.agents-mode` for future operator-mode changes.

## Rules

- Be concise in explanations — the catalog has the details.
- Accept shorthand answers ("tdd", "80", "conventional", "trunk", etc.).
- If the user gives a custom answer that doesn't match an option, record it as-is.
- Do not invent extra `agents-mode` keys beyond the canonical Claude-line schema.
- Preserve unknown keys in `.claude/.agents-mode` when updating.
- Do not change any other section of CLAUDE.md.

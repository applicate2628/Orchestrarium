# Initialize Project Policies

You are guiding the user through project policy configuration for the Claude Code pack.

## Continuity contract

- Follow the shared **Primary-task continuity and side work** rule in AGENTS.md; retain the admitted primary outcome and next authorized action.
- Answer brief questions inline. Promptly delegate eligible substantive admitted side work to matching non-spawning specialists under existing authority, capacity, full resource surfaces and gates; continue ready primary work in the same turn without waiting for the side result.
- Defer conflicting side work with its owner/resume point or use already-authorized validated isolation; preserve manual modes and explicit user stop/pause/cancel/reprioritization and native Goal holds.
- After an accepted phase or completed batch, continue to the next clear step unless a real gate blocks progression.
- Before claiming completion, reconcile the current result against the original request and any still-open required follow-up inside the same task.
- If a required next action is already known and still inside the current task, keep the task open instead of stopping at a partial batch.

## Steps

1. **Read current state.**
   - Read `.claude/CLAUDE.md` and check if a `## Project policies` section already exists.
   - Use the installed dispatch owner's effective read order to inspect only `consultantMode` and `mcpMode` in memory. Show their effective values and origins without creating or rewriting any file.
   - Inspect `.claude/.agents-mode.yaml` only as needed to plan a requested local edit. An inherited or preexisting value does not authorize a write.

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

4. **Select optional project preferences.**
   - Consultant: leave unchanged, prefer external (`consultantMode: external`), or off (`consultantMode: disabled`). An existing legacy `internal` value is not external authorization; leave it intact unless explicitly changed.
   - Relevant tools: leave unchanged, use fitting available tools as needed (`mcpMode: auto`), or require actual use of selected relevant, available skills, plugins and MCP tools (`mcpMode: force`). Force imposes no tool count or authority to install, enable, make network requests or spend. If fitting tools are unavailable, report the limit and continue unaffected work.
   - Neither choice authorizes launch, fallback or spending. Init itself does not launch external providers.

5. **Confirm the intended writes.**
   - Show the policy changes and only the explicitly selected local mode keys. Omission means no edit for that key. Ask before writing.

6. **Write only selected project-local keys.**
   - If neither mode key changes, leave `.claude/.agents-mode.yaml` untouched; if absent, do not create it.
   - Update only the selected top-level scalars. Preserve all unrelated bytes, including unknown or old keys, comments and formatting. Do not copy inherited values, expand presets, normalize the whole file, recreate legacy files, or modify global files. If the edit cannot safely preserve other content, leave the file unchanged and say why.

   Use this canonical shape for selected keys only:

   ```yaml
   consultantMode: {value}  # selectable here: external | disabled
   mcpMode: {value}  # selectable here: auto | force
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
   - Report saved policy changes and whether a preference was updated.
   - Mention `/agents-policies` to view project policies later.
   - Mention `.claude/.agents-mode.yaml` for future operator-mode changes.

## Rules

- Be concise in explanations — the catalog has the details.
- Accept shorthand answers ("tdd", "80", "conventional", "trunk", etc.).
- If the user gives a custom answer that doesn't match an option, record it as-is.
- Do not invent extra `agents-mode` keys beyond the canonical Claude-line schema.
- Preserve unknown keys in `.claude/.agents-mode.yaml` when updating.
- For decision-driving reads, use the dispatch owner's per-key precedence (local `.claude/.agents-mode.yaml`, local legacy `.claude/.agents-mode`, pack-local global `~/.claude/.agents-mode.yaml`, pack-local global legacy `~/.claude/.agents-mode`, shared cross-pack global `~/.agents-mode.yaml`, then built-in defaults) and the read-only resolution in Step 1; inspection grants no write to the source overlay. Persist only the explicitly selected authorized project configuration in Step 6.
- Do not change any other section of CLAUDE.md.

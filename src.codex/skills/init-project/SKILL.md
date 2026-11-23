---
name: init-project
description: "AGENTS.md policies, .agents-mode.yaml bootstrap."
---

# Init Project

Guide the user through first-time Codex project bootstrap for project policies and operator mode state.

## Continuity contract

- Follow the shared **Primary-task continuity and side work** rule in AGENTS.md; retain the admitted primary outcome and next authorized action.
- Answer brief questions inline. Promptly delegate eligible substantive admitted side work to matching non-spawning specialists under existing authority, capacity, full resource surfaces and gates; continue ready primary work in the same turn without waiting for the side result.
- Defer conflicting side work with its owner/resume point or use already-authorized validated isolation; preserve manual modes and explicit user stop/pause/cancel/reprioritization and native Goal holds.
- After an accepted phase or completed batch, continue to the next clear step unless a real gate blocks progression.
- Before claiming completion, reconcile the current result against the original request and any still-open required follow-up inside the same task.
- If a required next action is already known and still inside the current task, keep the task open instead of stopping at a partial batch.

## Steps

1. **Read current state.**
   - Read the project's root `AGENTS.md` and check whether a `## Project policies` section already exists.
   - Use the installed dispatch owner's effective read order to inspect only `consultantMode` and `mcpMode` in memory. Show their effective values and origins without creating or rewriting any file.
   - Inspect `.agents/.agents-mode.yaml` only as needed to plan a requested local edit. An inherited or preexisting value does not authorize a write.

2. **Read the installed canonical sources.**
   - Read the installed policy catalog from `../lead/policies-catalog.md`.
   - Read the installed Codex dispatch contract from `../lead/external-dispatch.md`.
   - Use those two files as the canonical source for policy choices, allowed `agents-mode` values, and write rules instead of inventing parallel semantics.

3. **Configure project policies.**
   - Walk through each policy area from the catalog one at a time.
   - For each area:
     - state the policy name and question
     - list the allowed options with concise descriptions
     - show the default
     - accept shorthand answers or the default
   - If the user says "defaults for the rest" or similar, apply defaults to all remaining policy areas.

4. **Select optional project preferences.**
   - Consultant: leave unchanged, prefer external (`consultantMode: external`), or off (`consultantMode: disabled`). An existing legacy `internal` value is not external authorization; leave it intact unless explicitly changed.
   - Relevant tools: leave unchanged, use fitting available tools as needed (`mcpMode: auto`), or require actual use of selected relevant, available skills, plugins and MCP tools (`mcpMode: force`). Force imposes no tool count or authority to install, enable, make network requests or spend. If fitting tools are unavailable, report the limit and continue unaffected work.
   - Neither choice authorizes launch, fallback or spending. Init itself does not launch external providers.

5. **Confirm the intended writes.**
   - Show the policy changes and only the explicitly selected local mode keys. Omission means no edit for that key. Ask before writing.

6. **Write only selected project-local keys.**
   - If neither mode key changes, leave `.agents/.agents-mode.yaml` untouched; if absent, do not create it.
   - Update only the selected top-level scalars. Preserve all unrelated bytes, including unknown or old keys, comments and formatting. Do not copy inherited values, expand presets, normalize the whole file, recreate legacy files, or modify global files. If the edit cannot safely preserve other content, leave the file unchanged and say why.

   Use this canonical shape for selected keys only:

   ```yaml
   consultantMode: {value}  # selectable here: external | disabled
   mcpMode: {value}  # selectable here: auto | force
   ```

7. **Write `## Project policies` to `AGENTS.md`.**
   - Add or replace only the `## Project policies` section in the project's root `AGENTS.md`.
   - If the section already exists, update it in place.
   - If it does not exist, append it at the end of the file so it stays user-managed outside the installed pack content.
   - Use this rendered format:

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
   - Mention `$second-opinion` for later consultant toggle changes.

## Rules

- Be concise; the catalog and dispatch contract hold the details.
- Do not invent extra policy keys or extra `agents-mode` keys.
- Preserve unknown keys in `.agents/.agents-mode.yaml` when updating.
- For decision-driving reads, use the dispatch owner's per-key precedence (local `.agents/.agents-mode.yaml`, local legacy `.agents/.agents-mode`, pack-local global `~/.codex/.agents-mode.yaml`, pack-local global legacy `~/.codex/.agents-mode`, shared cross-pack global `~/.agents-mode.yaml`, then built-in defaults) and the read-only resolution in Step 1; inspection grants no write to the source overlay. Persist only the explicitly selected authorized project configuration in Step 6.
- Do not modify any other section of `AGENTS.md`.
- Treat root `AGENTS.md` as the project-runtime target, not the Orchestrarium monorepo maintenance overlay.

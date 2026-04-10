---
name: init-project
description: Configure project policies in the root AGENTS.md and initialize or update .agents/.agents-mode for the current project.
---

# Init Project

Guide the user through first-time Codex project bootstrap for project policies and operator mode state.

## Steps

1. **Read current state.**
   - Read the project's root `AGENTS.md` and check whether a `## Project policies` section already exists.
   - Read `.agents/.agents-mode` first; if it is missing, read legacy `.agents/.consultant-mode` only as migration input.
   - If either surface already exists, show the current values and ask whether to keep them, review them, or start fresh.

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

4. **Configure operator modes.**
   - Walk through the canonical `agents-mode` keys one at a time:
     - `consultantMode`
     - `delegationMode`
     - `mcpMode`
     - `preferExternalWorker`
     - `preferExternalReviewer`
     - `externalProvider`
     - `externalClaudeSecretMode`
     - `externalClaudeProfile`
   - Use the existing value when present; otherwise default to:
     - `consultantMode: disabled`
     - `delegationMode: manual`
     - `mcpMode: auto`
     - `preferExternalWorker: false`
     - `preferExternalReviewer: false`
     - `externalProvider: auto`
     - `externalClaudeSecretMode: auto`
     - `externalClaudeProfile: sonnet-high`
   - Accept shorthand answers such as `force`, `external reviewer only`, `opus`, or `defaults for the rest`.

5. **Confirm the final choices.**
   - Present one summary table for `## Project policies`.
   - Present one summary table for `.agents/.agents-mode`.
   - Ask for confirmation before writing.

6. **Write `.agents/.agents-mode`.**
   - Write the canonical file to `.agents/.agents-mode`.
   - Preserve unknown keys when updating an existing file.
   - If only legacy `.agents/.consultant-mode` exists, use it as migration input but write the canonical file to `.agents/.agents-mode`.
   - Keep one key per line and include the inline allowed-values comment for every canonical key.
   - Do not create a new legacy `.agents/.consultant-mode` file.

   Use this canonical shape:

   ```yaml
   consultantMode: {value}  # allowed: external | auto | internal | disabled
   delegationMode: {value}  # allowed: manual | auto | force
   mcpMode: {value}  # allowed: auto | force
   preferExternalWorker: {value}  # allowed: false | true
   preferExternalReviewer: {value}  # allowed: false | true
   externalProvider: {value}  # allowed here: auto | claude | gemini
   externalClaudeSecretMode: {value}  # allowed when Claude is selectable: auto | force
   externalClaudeProfile: {value}  # allowed: sonnet-high | opus-max
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
   - Tell the user the project policies and operator mode file are saved.
   - Mention `$second-opinion` for later consultant-mode changes.

## Rules

- Be concise; the catalog and dispatch contract hold the details.
- Do not invent extra policy keys or extra `agents-mode` keys.
- Preserve unknown keys in `.agents/.agents-mode` when updating.
- Do not modify any other section of `AGENTS.md`.
- Treat root `AGENTS.md` as the project-runtime target, not the Orchestrarium monorepo maintenance overlay.

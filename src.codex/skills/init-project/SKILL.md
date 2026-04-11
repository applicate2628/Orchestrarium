---
name: init-project
description: Configure project policies in the root AGENTS.md and initialize or update .agents/.agents-mode for the current project.
---

# Init Project

Guide the user through first-time Codex project bootstrap for project policies and operator mode state.

## Continuity contract

- Use one primary in-progress task at a time.
- Side requests may temporarily interrupt that task, but they do not replace it unless the user explicitly reprioritizes, cancels, or parks it.
- After any side request, explicitly resume the primary task and state the next concrete step.
- After an accepted phase or completed batch, continue to the next clear step unless a real gate blocks progression.
- Before claiming completion, reconcile the current result against the original request and any still-open required follow-up inside the same task.
- If a required next action is already known and still inside the current task, keep the task open instead of stopping at a partial batch.

## Steps

1. **Read current state.**
   - Read the project's root `AGENTS.md` and check whether a `## Project policies` section already exists.
   - Read `.agents/.agents-mode` first.
   - If `.agents/.agents-mode` already exists, normalize it to the current canonical format before presenting or trusting the current values.
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
     - `externalCodexWorkdirMode`
     - `externalClaudeWorkdirMode`
     - `externalGeminiWorkdirMode`
     - `externalClaudeSecretMode`
     - `externalClaudeApiMode`
     - `externalClaudeProfile`
   - Use the existing value when present; otherwise default to:
     - `consultantMode: disabled`
     - `delegationMode: manual`
     - `mcpMode: auto`
   - `preferExternalWorker: false`
   - `preferExternalReviewer: false`
   - `externalProvider: auto`
   - `externalPriorityProfile: balanced`
   - shipped `externalPriorityProfiles`
   - `externalOpinionCounts` defaulting each documented lane to `1`
   - `externalCodexWorkdirMode: neutral`
   - `externalClaudeWorkdirMode: neutral`
   - `externalGeminiWorkdirMode: neutral`
   - `externalClaudeSecretMode: auto`
   - `externalClaudeApiMode: auto`
   - `externalClaudeProfile: sonnet-high`
   - Accept shorthand answers such as `force`, `external reviewer only`, `opus`, or `defaults for the rest`.

5. **Confirm the final choices.**
   - Present one summary table for `## Project policies`.
   - Present one summary table for `.agents/.agents-mode`.
   - Ask for confirmation before writing.

6. **Write `.agents/.agents-mode`.**
   - Write the canonical file to `.agents/.agents-mode`.
   - Preserve unknown keys when updating an existing file.
   - Treat comment-free, partial, or older-layout files as legacy input and rewrite them to the current canonical format instead of preserving stale layout.
   - Keep one key per line and include the inline allowed-values comment for every canonical key.
   - Refresh the shipped `externalPriorityProfiles` and `externalOpinionCounts` blocks to the current pack version while preserving the effective values of known keys and any unknown keys.

   Use this canonical shape:

   ```yaml
   consultantMode: {value}  # allowed: external | internal | disabled
   delegationMode: {value}  # allowed: manual | auto | force
   mcpMode: {value}  # allowed: auto | force
   preferExternalWorker: {value}  # allowed: false | true
   preferExternalReviewer: {value}  # allowed: false | true
   externalProvider: {value}  # allowed here: auto | codex | claude | gemini
   externalPriorityProfile: {value}  # allowed: balanced | gemini-crosscheck | <repo-local profile>
   externalPriorityProfiles: {value}  # allowed: structured profile map
   externalOpinionCounts: {value}  # allowed: structured lane-count map
   externalCodexWorkdirMode: {value}  # allowed: neutral | project
   externalClaudeWorkdirMode: {value}  # allowed: neutral | project
   externalGeminiWorkdirMode: {value}  # allowed: neutral | project
   externalClaudeSecretMode: {value}  # allowed when Claude is selectable: auto | force
   externalClaudeApiMode: {value}  # allowed when Claude is selectable: disabled | auto | force
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
   - Mention `$second-opinion` for later consultant toggle changes.

## Rules

- Be concise; the catalog and dispatch contract hold the details.
- Do not invent extra policy keys or extra `agents-mode` keys.
- Preserve unknown keys in `.agents/.agents-mode` when updating.
- Any read of `.agents/.agents-mode` that drives a decision should normalize the file to the current canonical format before trusting the flags.
- Do not modify any other section of `AGENTS.md`.
- Treat root `AGENTS.md` as the project-runtime target, not the Orchestrarium monorepo maintenance overlay.

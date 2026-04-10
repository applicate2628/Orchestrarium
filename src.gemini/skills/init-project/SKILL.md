---
name: init-project
description: >
  Bootstrap Orchestrarium's shared-routing overlay for Gemini after the official
  Gemini /init step has created or refreshed GEMINI.md.
---

# Init Project

Use this helper after Gemini's built-in `/init` has already created or refreshed the project's `GEMINI.md`.

This helper owns only the Orchestrarium overlay file:

- `.gemini/.agents-mode`

It must not replace Gemini's official runtime config in:

- `.gemini/settings.json`

## Continuity contract

- Use one primary in-progress task at a time.
- Side requests may temporarily interrupt that task, but they do not replace it unless the user explicitly reprioritizes, cancels, or parks it.
- After any side request, explicitly resume the primary task and state the next concrete step.
- After an accepted phase or completed batch, continue to the next clear step unless a real gate blocks progression.
- Before claiming completion, reconcile the current result against the original request and any still-open required follow-up inside the same task.
- If a required next action is already known and still inside the current task, keep the task open instead of stopping at a partial batch.

## Steps

1. **Verify the official Gemini bootstrap first.**
   - Read the project's `GEMINI.md`.
   - If `GEMINI.md` is missing, stop and tell the user to run Gemini's built-in `/init` first.
   - Treat `/init` as the canonical owner for creating or refreshing `GEMINI.md`.

2. **Read current overlay state.**
   - Read `.gemini/.agents-mode` if it exists.
   - If it is missing, start from the canonical defaults below.
   - Preserve unknown keys when updating an existing file.

3. **Read the canonical operator reference.**
   - Read `../../../docs/agents-mode-reference.md`.
   - Use it as the canonical source for key meanings, allowed values, and write rules.

4. **Configure the shared routing overlay.**
   - Walk through these keys one at a time:
     - `consultantMode`
     - `delegationMode`
     - `mcpMode`
     - `preferExternalWorker`
     - `preferExternalReviewer`
     - `externalProvider`
     - `externalClaudeSecretMode`
    - Use existing values when present; otherwise default to:
      - `consultantMode: disabled`
      - `delegationMode: manual`
      - `mcpMode: auto`
      - `preferExternalWorker: false`
      - `preferExternalReviewer: false`
      - `externalProvider: auto`
      - `externalClaudeSecretMode: auto`
   - Accept shorthand such as `force`, `external reviewer only`, or `defaults for the rest`.

5. **Confirm before writing.**
   - Present one summary table for the final `.gemini/.agents-mode` values.
   - Tell the user explicitly that `.gemini/settings.json` stays untouched by this helper.
   - Ask for confirmation before writing.

6. **Write `.gemini/.agents-mode`.**
   - Keep one key per line.
   - Keep inline allowed-values comments on every canonical key.
   - Use this canonical Gemini-line shape:

   ```yaml
   consultantMode: {value}  # allowed: external | auto | internal | disabled
   delegationMode: {value}  # allowed: manual | auto | force
   mcpMode: {value}  # allowed: auto | force
   preferExternalWorker: {value}  # allowed: false | true
   preferExternalReviewer: {value}  # allowed: false | true
   externalProvider: {value}  # allowed here: auto | codex | claude
   externalClaudeSecretMode: {value}  # allowed when Claude is selected: auto | force
   ```

7. **Confirm completion.**
   - Tell the user the Gemini official surfaces are split correctly:
     - `/init` owns `GEMINI.md`
     - `.gemini/settings.json` remains Gemini-native runtime config
     - `.gemini/.agents-mode` now holds the Orchestrarium shared-routing overlay

## Rules

- Do not create or rewrite `.gemini/settings.json`.
- Do not pretend `.gemini/.agents-mode` is a Gemini-native runtime setting.
- Do not invent extra keys beyond the canonical overlay schema.
- If the user asks for `externalProvider: gemini` on the Gemini line, treat it as a configuration error instead of writing a self-referential provider selection.

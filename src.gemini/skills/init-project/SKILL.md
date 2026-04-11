---
name: init-project
description: >
  Review or update Orchestrarium's installed shared-routing overlay for Gemini
  after the official Gemini /init step has created or refreshed GEMINI.md.
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
   - If the file exists, normalize it to the current canonical format before presenting or trusting any values.
   - If it is missing, start from the canonical defaults below.
   - Preserve unknown keys when updating an existing file.

3. **Read the canonical operator reference when it is available.**
   - If the current repository includes `docs/agents-mode-reference.md`, read it and use it as the authoritative value-by-value reference.
   - If that document is not present in the installed runtime, rely on this skill's canonical schema and rules below instead of inventing extra Gemini-only keys.

4. **Configure the shared routing overlay.**
   - Walk through these keys one at a time:
     - `consultantMode`
     - `delegationMode`
     - `mcpMode`
     - `preferExternalWorker`
     - `preferExternalReviewer`
     - `externalProvider`
     - `externalPriorityProfile`
     - `externalPriorityProfiles`
     - `externalOpinionCounts`
     - `externalCodexWorkdirMode`
     - `externalClaudeWorkdirMode`
     - `externalGeminiWorkdirMode`
     - `externalClaudeSecretMode`
     - `externalClaudeApiMode`
   - Use existing values when present; otherwise default to:
     - `consultantMode: disabled`
     - `delegationMode: manual`
     - `mcpMode: auto`
     - `preferExternalWorker: false`
     - `preferExternalReviewer: false`
     - `externalProvider: auto`  (shared-universe default; lane-driven via active profile)
     - `externalPriorityProfile: balanced`
     - `externalPriorityProfiles.balanced`: current shared matrix
     - `externalPriorityProfiles.gemini-crosscheck`: Gemini present in non-visual advisory and pre-PR review cross-check lanes
     - `externalOpinionCounts`: `1` for ordinary lanes unless a repo-local policy explicitly asks for more
     - `externalCodexWorkdirMode: neutral`
     - `externalClaudeWorkdirMode: neutral`
     - `externalGeminiWorkdirMode: neutral`
     - `externalClaudeSecretMode: auto`
     - `externalClaudeApiMode: auto`
   - Accept shorthand such as `force`, `external reviewer only`, `balanced profile`, or `gemini crosscheck`.

5. **Confirm before writing.**
   - Present one summary table for the final `.gemini/.agents-mode` values.
   - Tell the user explicitly that `.gemini/settings.json` stays untouched by this helper.
   - Ask for confirmation before writing.

6. **Write `.gemini/.agents-mode`.**
   - Keep one key per line.
   - Treat comment-free, partial, or older-layout files as legacy input and rewrite them to the current canonical format instead of preserving stale layout.
   - Keep inline allowed-values comments on every canonical scalar key and preserve the multiline `externalPriorityProfiles` / `externalOpinionCounts` blocks verbatim.
   - Refresh the shipped profile/count blocks to the current pack version while preserving effective known values and any unknown keys.
   - Use this canonical Gemini-line shape:

   ```yaml
   consultantMode: {value}  # allowed: external | internal | disabled
   delegationMode: {value}  # allowed: manual | auto | force
   mcpMode: {value}  # allowed: auto | force
   preferExternalWorker: {value}  # allowed: false | true
   preferExternalReviewer: {value}  # allowed: false | true
   externalProvider: {value}  # allowed here: auto | codex | claude | gemini
   externalPriorityProfile: {value}  # allowed: balanced | gemini-crosscheck
   externalPriorityProfiles:
     balanced:
       advisory.repo-understanding: [claude, gemini, codex]
       advisory.design-adr: [claude, codex, gemini]
       review.pre-pr: [claude, codex, gemini]
       worker.default-implementation: [codex, claude, gemini]
       worker.long-autonomous: [claude, codex, gemini]
       worker.visual-icon-decorative: [gemini, claude, codex]
       review.visual: [gemini, claude, codex]
     gemini-crosscheck:
       advisory.repo-understanding: [claude, gemini, codex]
       advisory.design-adr: [claude, gemini, codex]
       review.pre-pr: [claude, gemini, codex]
       worker.default-implementation: [codex, claude, gemini]
       worker.long-autonomous: [claude, codex, gemini]
       worker.visual-icon-decorative: [gemini, claude, codex]
       review.visual: [gemini, claude, codex]
   externalOpinionCounts:
     advisory.repo-understanding: 1
     advisory.design-adr: 1
     review.pre-pr: 1
     worker.default-implementation: 1
     worker.long-autonomous: 1
     worker.visual-icon-decorative: 1
     review.visual: 1
   externalCodexWorkdirMode: {value}  # allowed: neutral | project
   externalClaudeWorkdirMode: {value}  # allowed: neutral | project
   externalGeminiWorkdirMode: {value}  # allowed: neutral | project
   externalClaudeSecretMode: {value}  # allowed when Claude is selected: auto | force
   externalClaudeApiMode: {value}  # allowed when Claude is selected: disabled | auto | force
   ```

7. **Confirm completion.**
   - Tell the user the Gemini official surfaces are split correctly:
     - `/init` owns `GEMINI.md`
     - `.gemini/settings.json` remains Gemini-native runtime config
     - `.gemini/.agents-mode` now holds the Orchestrarium shared-routing overlay, including the named priority profiles and lane opinion counts

## Rules

- Do not create or rewrite `.gemini/settings.json`.
- Do not pretend `.gemini/.agents-mode` is a Gemini-native runtime setting.
- Do not invent extra keys beyond the canonical overlay schema.
- Any read of `.gemini/.agents-mode` that drives a decision should normalize the file to the current canonical format before trusting the flags.
- If the user asks for `externalProvider: gemini` on the Gemini line, accept it only as an explicit self-provider override; ordinary `auto` routing must still avoid same-provider self-bounce.

---
name: init-project
description: >
  Review or update Orchestrarium's installed shared-routing overlay for Gemini
  after the official Gemini /init step has created or refreshed GEMINI.md.
---

# Init Project

Use this helper after Gemini's built-in `/init` has already created or refreshed the project's `GEMINI.md`.

This helper owns only the Orchestrarium overlay file:

- `.gemini/.agents-mode.yaml`

It must not replace Gemini's official runtime config in:

- `.gemini/settings.json`

## Continuity contract

- Use one primary in-progress task at a time.
- Side requests may temporarily interrupt that task, but they do not replace it unless the user explicitly reprioritizes, cancels, or parks it.
- After any side request, explicitly resume the primary task and state the next concrete step.
- After an accepted phase or completed batch, continue to the next clear step unless a real gate blocks progression.
- Before claiming completion, reconcile the current result against the original request and any still-open required follow-up inside the same task.
- If a required next action is already known and still inside the current task, keep the task open instead of stopping at a partial batch.

## Preset expansion table

Presets are init-time shortcuts only. They expand into canonical `agents-mode` keys. The preset name is NOT persisted in the file.

| Key | `default` (safe-init) | `absolute-balance` (everyday center) | `external-aggressive` (aggressive external use) | `correctness-first` (no-time-limit correctness) | `max-speed` (speed-first) |
|---|---|---|---|---|---|
| `consultantMode` | `disabled` | `internal` | `external` | `external` | `disabled` |
| `delegationMode` | `manual` | `auto` | `force` | `force` | `auto` |
| `mcpMode` | `auto` | `auto` | `auto` | `force` | `auto` |
| `preferExternalWorker` | `false` | `false` | `true` | `true` | `false` |
| `preferExternalReviewer` | `false` | `true` | `true` | `true` | `false` |
| `externalProvider` | `auto` | `auto` | `auto` | `auto` | `auto` |
| `externalPriorityProfile` | `balanced` | `balanced` | `balanced` | `gemini-crosscheck` | `balanced` |
| `externalPriorityProfiles` | shipped as-is | shipped as-is | shipped as-is | shipped as-is | shipped as-is |
| `externalOpinionCounts` | all `1` | all `1` | all `1` | advisory+review lanes `2`, others `1` | all `1` |
| `externalCodexWorkdirMode` | `neutral` | `neutral` | `neutral` | `neutral` | `project` |
| `externalClaudeWorkdirMode` | `neutral` | `neutral` | `neutral` | `neutral` | `project` |
| `externalGeminiWorkdirMode` | `neutral` | `neutral` | `neutral` | `neutral` | `project` |
| `externalModelMode` | `runtime-default` | `runtime-default` | `runtime-default` | `pinned-top-pro` | `runtime-default` |
| `externalGeminiFallbackMode` | `auto` | `auto` | `auto` | `auto` | `auto` |
| `externalClaudeSecretMode` | `auto` | `auto` | `auto` | `auto` | `auto` |
| `externalClaudeApiMode` | `auto` | `auto` | `auto` | `auto` | `auto` |

`correctness-first` lane-specific opinion counts:
- `advisory.repo-understanding: 2`
- `advisory.design-adr: 2`
- `review.pre-pr: 2`
- `review.performance-architecture: 2`
- all other lanes: `1`

Routing conventions (not persisted as keys):
- **same-host fast-path**: under `external-aggressive` and `max-speed`, when neutral isolation is not required, allow per-invocation explicit self-provider override. Keep the stored file canonical; this is a routing rule, not a persisted key.
- **overflow means spill, not serialize**: under `external-aggressive`, internal slot saturation pushes independent eligible lanes into `$external-worker`, `$external-reviewer`, or `$external-brigade` by default.

## Steps

1. **Verify the official Gemini bootstrap first.**
   - Read the project's `GEMINI.md`.
   - If `GEMINI.md` is missing, stop and tell the user to run Gemini's built-in `/init` first.
   - Treat `/init` as the canonical owner for creating or refreshing `GEMINI.md`.

2. **Read current overlay state.**
   - Read `.gemini/.agents-mode.yaml` first.
   - If it is missing, read legacy `.gemini/.agents-mode` as compatibility input only.
   - If either file exists, normalize it to the current canonical format before presenting or trusting any values.
   - Any read of `.gemini/.agents-mode.yaml` that drives a decision should normalize the file to the current canonical format before trusting the flags.
   - If it is missing, start from the canonical defaults below.
   - Preserve unknown keys when updating an existing file.

3. **Read the canonical operator reference when it is available.**
   - If the current repository includes `docs/agents-mode-reference.md`, read it and use it as the authoritative value-by-value reference.
   - If that document is not present in the installed runtime, rely on this skill's canonical schema and rules below instead of inventing extra Gemini-only keys.

4. **Select a preset (optional).**
    - Ask the user if they want to start from a preset: `default`, `absolute-balance`, `external-aggressive`, `correctness-first`, or `max-speed`.
    - If the user picks a preset, apply its full key expansion from the table above as the starting values.
    - If the user says "custom" or skips this step, start from the `default` baseline.
    - After applying a preset, still walk through each key so the user can fine-tune individual values.
    - The preset name is NOT persisted — only the expanded canonical keys are written.

5. **Configure the shared routing overlay.**
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
     - `externalModelMode`
     - `externalGeminiFallbackMode`
     - `externalClaudeSecretMode`
     - `externalClaudeApiMode`
   - Use existing values when present, the preset-expanded value if one was selected, or otherwise default to:
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
     - `externalGeminiFallbackMode: auto`
     - `externalClaudeSecretMode: auto`
     - `externalClaudeApiMode: auto`
   - Accept shorthand such as `force`, `external reviewer only`, `balanced profile`, or `gemini crosscheck`.

6. **Confirm before writing.**
   - Present one summary table for the final `.gemini/.agents-mode.yaml` values.
   - Tell the user explicitly that `.gemini/settings.json` stays untouched by this helper.
   - Ask for confirmation before writing.

7. **Write `.gemini/.agents-mode.yaml`.**
   - Keep one key per line.
   - Treat comment-free, partial, or older-layout files as legacy input and rewrite them to the current canonical format instead of preserving stale layout.
   - Do not recreate legacy `.gemini/.agents-mode`; write the canonical output only to `.gemini/.agents-mode.yaml`.
   - Keep inline comments on every canonical scalar key plus every shipped `externalPriorityProfiles` / `externalOpinionCounts` entry, and preserve the multiline blocks verbatim.
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
       review.performance-architecture: [claude, codex, gemini]
       worker.default-implementation: [codex, claude, gemini]
       worker.systems-performance-implementation: [codex, claude, gemini]
       worker.long-autonomous: [claude, codex, gemini]
       worker.ui-structural-modernization: [gemini, claude, codex]
       worker.ui-surgical-patch-cleanup: [claude, codex, gemini]
       worker.visual-icon-decorative: [gemini, claude, codex]
       review.visual: [gemini, claude, codex]
     gemini-crosscheck:
       advisory.repo-understanding: [claude, gemini, codex]
       advisory.design-adr: [claude, gemini, codex]
       review.pre-pr: [claude, gemini, codex]
       review.performance-architecture: [claude, codex, gemini]
       worker.default-implementation: [codex, claude, gemini]
       worker.systems-performance-implementation: [codex, claude, gemini]
       worker.long-autonomous: [claude, gemini, codex]
       worker.ui-structural-modernization: [gemini, claude, codex]
       worker.ui-surgical-patch-cleanup: [claude, codex, gemini]
       worker.visual-icon-decorative: [gemini, claude, codex]
       review.visual: [gemini, claude, codex]
   externalOpinionCounts:
     advisory.repo-understanding: 1
     advisory.design-adr: 1
     review.pre-pr: 1
     review.performance-architecture: 1
     worker.default-implementation: 1
     worker.systems-performance-implementation: 1
     worker.long-autonomous: 1
     worker.ui-structural-modernization: 1
     worker.ui-surgical-patch-cleanup: 1
     worker.visual-icon-decorative: 1
     review.visual: 1
   externalCodexWorkdirMode: {value}  # allowed: neutral | project
   externalClaudeWorkdirMode: {value}  # allowed: neutral | project
   externalGeminiWorkdirMode: {value}  # allowed: neutral | project
   externalModelMode: {value}  # allowed: runtime-default | pinned-top-pro
   externalGeminiFallbackMode: {value}  # allowed when Gemini is selected: disabled | auto | force
   externalClaudeSecretMode: {value}  # allowed when Claude is selected: auto | force
   externalClaudeApiMode: {value}  # allowed when Claude is selected: disabled | auto | force
   ```

8. **Confirm completion.**
   - Tell the user the Gemini official surfaces are split correctly:
     - `/init` owns `GEMINI.md`
     - `.gemini/settings.json` remains Gemini-native runtime config
     - `.gemini/.agents-mode.yaml` now holds the Orchestrarium shared-routing overlay, including the named priority profiles and lane opinion counts

## Rules

- Do not create or rewrite `.gemini/settings.json`.
- Do not pretend `.gemini/.agents-mode.yaml` is a Gemini-native runtime setting.
- Do not invent extra keys beyond the canonical overlay schema.
- Any read that drives a decision should prefer `.gemini/.agents-mode.yaml`, fall back to legacy `.gemini/.agents-mode` only if the canonical file is missing, normalize either input forward into `.gemini/.agents-mode.yaml`, and not recreate the legacy file.
- If the user asks for `externalProvider: gemini` on the Gemini line, accept it only as an explicit self-provider override; ordinary `auto` routing must still avoid same-provider self-bounce.

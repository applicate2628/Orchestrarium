---
name: init-project
description: >
  Review or update Orchestrarium's installed shared-routing overlay for Qwen
  after the official Qwen /init step has created or refreshed QWEN.md.
---

# Init Project

Use this helper after Qwen's built-in `/init` has already created or refreshed the project's `QWEN.md`.

This helper owns only the Orchestrarium overlay file:

- `.qwen/.agents-mode.yaml`

It must not replace Qwen's official runtime config in:

- `.qwen/settings.json`

## Continuity contract

- Use one primary in-progress task at a time.
- Side requests may temporarily interrupt that task, but they do not replace it unless the user explicitly reprioritizes, cancels, or parks it.
- After any side request, explicitly resume the primary task and state the next concrete step.
- After an accepted phase or completed batch, continue to the next clear step unless a real gate blocks progression.
- Before claiming completion, reconcile the current result against the original request and any still-open required follow-up inside the same task.
- If a required next action is already known and still inside the current task, keep the task open instead of stopping at a partial batch.

## Preset expansion table

Presets are init-time shortcuts only. They expand into canonical `agents-mode` keys. The preset name is NOT persisted in the file.

| Preset | Intent | Expansion summary |
|---|---|---|
| `default` | safe baseline | `consultantMode: disabled`, `delegationMode: manual`, `parallelMode: auto`, `mcpMode: auto`, `externalProvider: auto`, `externalPriorityProfile: balanced`, `externalModelMode: runtime-default` |
| `absolute-balance` | everyday center | `consultantMode: internal`, `delegationMode: auto`, `preferExternalReviewer: true`, keep `externalProvider: auto` and the shipped `balanced` profile |
| `external-aggressive` | spill eligible independent lanes outward sooner | `consultantMode: external`, `delegationMode: force`, `parallelMode: force`, `preferExternalWorker: true`, `preferExternalReviewer: true`, keep `externalProvider: auto` and the shipped `balanced` profile |
| `correctness-first` | slower, more checking | `consultantMode: external`, `delegationMode: force`, `mcpMode: force`, `preferExternalWorker: true`, `preferExternalReviewer: true`, `externalModelMode: pinned-top-pro`, raise selected advisory and review opinion counts above `1` only when the user explicitly asks for that stricter lane policy |
| `max-speed` | fastest honest local routing | `consultantMode: disabled`, `delegationMode: auto`, `parallelMode: force`, `externalCodexWorkdirMode: project`, `externalClaudeWorkdirMode: project`, keep `externalProvider: auto` and the shipped `balanced` profile |

Routing conventions that are not persisted as keys:

- same-host self-provider routing stays explicit-only
- internal slot overflow should spill into eligible external adapters instead of silently serializing when the active routing policy allows it
- shipped production `auto` routing stays on `codex | claude`; `gemini` and `qwen` remain explicit `WEAK MODEL / NOT RECOMMENDED` example-only paths

## Steps

1. **Verify the official Qwen bootstrap first.**
   - Read the project's `QWEN.md`.
   - If `QWEN.md` is missing, stop and tell the user to run Qwen's built-in `/init` first.
   - Treat `/init` as the canonical owner for creating or refreshing `QWEN.md`.

2. **Read current overlay state.**
   - Read `.qwen/.agents-mode.yaml` first.
   - If it is missing, read legacy `.qwen/.agents-mode` as compatibility input only.
   - If both local files are missing, fall back to global `~/.qwen/.agents-mode.yaml` and then global legacy `~/.qwen/.agents-mode` as compatibility input.
   - If either file exists, normalize it to the current canonical format before presenting or trusting any values.
   - Any read of `.qwen/.agents-mode.yaml` that drives a decision should normalize the file to the current canonical format before trusting the flags.
   - If neither local nor global overlay exists, start from the canonical defaults below.
   - Preserve unknown keys when updating an existing file.

3. **Read the canonical operator reference when it is available.**
   - If the current repository includes `docs/agents-mode-reference.md`, read it and use it as the authoritative value-by-value reference.
   - If that document is not present in the installed runtime, rely on this skill's canonical schema and rules below instead of inventing extra Qwen-only keys.

4. **Select a preset (optional).**
   - Ask the user if they want to start from a preset: `default`, `absolute-balance`, `external-aggressive`, `correctness-first`, or `max-speed`.
   - If the user picks a preset, apply its key expansion from the table above as the starting values.
   - After applying a preset, ask whether to write that preset as-is or fine-tune individual keys first.
   - If the user says `use the preset`, `preset only`, `apply as-is`, or otherwise declines manual tweaking, skip the key-by-key overlay walkthrough and carry the preset-expanded values straight to confirmation.
   - If the user says `custom` or skips this step, start from the `default` baseline.
   - The preset name is NOT persisted; only the expanded canonical keys are written.

5. **Configure the shared routing overlay.**
   - Run this step only when the user started from `custom`, skipped preset selection, or explicitly asked to fine-tune after selecting a preset.
   - Walk through these keys one at a time:
     - `consultantMode`
     - `externalClaudeApiMode`
     - `delegationMode`
     - `parallelMode`
     - `mcpMode`
     - `preferExternalWorker`
     - `preferExternalReviewer`
     - `externalProvider`
     - `externalPriorityProfile`
     - `externalPriorityProfiles`
     - `externalOpinionCounts`
     - `externalCodexWorkdirMode`
     - `externalClaudeWorkdirMode`
     - `externalModelMode`
   - Use existing values when present, the preset-expanded value if one was selected, or otherwise default to:
     - `consultantMode: disabled`
     - `externalClaudeApiMode: auto`
     - `delegationMode: manual`
     - `parallelMode: auto`
     - `mcpMode: auto`
     - `preferExternalWorker: false`
     - `preferExternalReviewer: false`
     - `externalProvider: auto`
     - `externalPriorityProfile: balanced`
     - `externalPriorityProfiles.balanced`: current shared production matrix using `codex | claude` only
     - `externalOpinionCounts`: `1` for ordinary lanes unless a repo-local policy explicitly asks for more
     - `externalCodexWorkdirMode: neutral`
     - `externalClaudeWorkdirMode: neutral`
     - `externalModelMode: runtime-default`
   - Accept shorthand such as `force`, `external reviewer only`, `balanced profile`, `explicit qwen`, or `pinned top pro`.
   - Do not invent shipped profile names beyond `balanced`. If the user wants another profile, treat it as repo-local custom data and keep `gemini` / `qwen` out of any profile the user expects to behave as production `auto`.

6. **Confirm before writing.**
   - Present one summary table for the final `.qwen/.agents-mode.yaml` values.
   - Tell the user explicitly that `.qwen/settings.json` stays untouched by this helper.
   - Ask for confirmation before writing.

7. **Write `.qwen/.agents-mode.yaml`.**
   - Keep one key per line.
   - Treat comment-free, partial, or older-layout files as legacy input and rewrite them to the current canonical format instead of preserving stale layout.
   - Do not recreate legacy `.qwen/.agents-mode`; write the canonical output only to `.qwen/.agents-mode.yaml`.
   - Keep inline comments on every canonical scalar key plus every shipped `externalPriorityProfiles` / `externalOpinionCounts` entry, and preserve the multiline blocks verbatim.
   - Refresh the shipped profile/count blocks to the current pack version while preserving effective known values and any unknown keys.
   - Use this canonical Qwen-line shape:

   ```yaml
   consultantMode: {value}  # allowed: external | internal | disabled; default: disabled
   externalClaudeApiMode: {value}  # controls advisory/review-only claude-secret candidate: disabled | auto | force; default: auto
   delegationMode: {value}  # allowed: manual | auto | force; default: manual
   parallelMode: {value}  # allowed: manual | auto | force; default: auto
   mcpMode: {value}  # allowed: auto | force; default: auto
   preferExternalWorker: {value}  # allowed: false | true; default: false
   preferExternalReviewer: {value}  # allowed: false | true; default: false
   externalProvider: {value}  # allowed here: auto | codex | claude | gemini | qwen; default: auto; gemini/qwen are WEAK MODEL / NOT RECOMMENDED example-only routes
   externalPriorityProfile: {value}  # allowed: balanced | <repo-local production profile>; default: balanced
   externalPriorityProfiles:
     balanced:
       advisory.repo-understanding: [claude, codex]
       advisory.design-adr: [claude, codex]
       review.pre-pr: [claude, codex]
       review.performance-architecture: [claude, codex]
       worker.default-implementation: [codex, claude]
       worker.systems-performance-implementation: [codex, claude]
       worker.long-autonomous: [claude, codex]
       worker.ui-structural-modernization: [codex, claude]
       worker.ui-surgical-patch-cleanup: [codex, claude]
       worker.visual-icon-decorative: [codex, claude]
       review.visual: [claude, codex]
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
   externalCodexWorkdirMode: {value}  # allowed: neutral | project; default: neutral
   externalClaudeWorkdirMode: {value}  # allowed: neutral | project; default: neutral
   externalModelMode: {value}  # allowed: runtime-default | pinned-top-pro; default: runtime-default
   ```

8. **Confirm completion.**
   - Tell the user the Qwen official surfaces are split correctly:
     - `/init` owns `QWEN.md`
     - `.qwen/settings.json` remains Qwen-native runtime config
     - `.qwen/.agents-mode.yaml` now holds the Orchestrarium shared-routing overlay, including the shipped `balanced` profile and lane opinion counts

## Rules

- Do not create or rewrite `.qwen/settings.json`.
- Do not pretend `.qwen/.agents-mode.yaml` is a Qwen-native runtime setting.
- Do not invent extra keys beyond the canonical overlay schema.
- Any read that drives a decision should prefer local `.qwen/.agents-mode.yaml`, then local legacy `.qwen/.agents-mode`, then global `~/.qwen/.agents-mode.yaml`, then global legacy `~/.qwen/.agents-mode`; normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file.
- Keep the example-provider contract aligned with the accepted pack policy: shipped production `auto` routing stays `codex | claude`, while explicit `externalProvider: gemini` and `externalProvider: qwen` remain manual `WEAK MODEL / NOT RECOMMENDED` example-only overrides.

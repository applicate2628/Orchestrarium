---
name: init-project
description: "Project init: configure AGENTS.md and agent mode."
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

| Key | `default` (safe-init) | `absolute-balance` (everyday center) | `external-aggressive` (aggressive external use) | `correctness-first` (no-time-limit correctness) | `power-mode` (hardest-task maximum result) | `max-speed` (speed-first) |
|---|---|---|---|---|---|---|
| `consultantMode` | `disabled` | `internal` | `external` | `external` | `external` | `disabled` |
| `delegationMode` | `auto` | `auto` | `force` | `force` | `force` | `auto` |
| `parallelMode` | `auto` | `auto` | `force` | `auto` | `force` | `force` |
| `mcpMode` | `auto` | `auto` | `auto` | `force` | `force` | `auto` |
| `preferExternalWorker` | `false` | `false` | `true` | `true` | `true` | `false` |
| `preferExternalReviewer` | `false` | `true` | `true` | `true` | `true` | `false` |
| `externalProvider` | `auto` | `auto` | `auto` | `auto` | `auto` | `auto` |
| `externalPriorityProfile` | `balanced` | `balanced` | `balanced` | `balanced` | `quality-first` | `balanced` |
| `reserveResolver` | `claude-sonnet` | `claude-sonnet` | `claude-sonnet` | `claude-sonnet` | `claude-sonnet` | `claude-sonnet` |
| `externalPriorityProfiles` | shipped as-is | shipped as-is | shipped as-is | shipped as-is | shipped as-is | shipped as-is |
| `externalOpinionCounts` | all `1` | all `1` | all `1` | advisory+review lanes `2`, others `1` | advisory+review lanes `2`, others `1` | all `1` |
| `externalCodexWorkdirMode` | `neutral` | `neutral` | `neutral` | `neutral` | `neutral` | `project` |
| `externalClaudeWorkdirMode` | `neutral` | `neutral` | `neutral` | `neutral` | `neutral` | `project` |
| `externalModelMode` | `runtime-default` | `runtime-default` | `runtime-default` | `pinned-top-pro` | `pinned-top-pro` | `runtime-default` |
| `externalCodexProfile` | `gpt-5.6-sol-xhigh` | `default` | `default` | `gpt-5.6-sol-xhigh` | `gpt-5.6-sol-xhigh` | `gpt-5.6-terra` |

`correctness-first` and `power-mode` lane-specific opinion counts:
- `advisory.repo-understanding: 2`
- `advisory.design-adr: 2`
- `review.pre-pr: 2`
- `review.security: 2`
- `review.performance-architecture: 2`
- `review.ui-visual-correctness: 2`
- all other lanes: `1`

Routing conventions (not persisted as keys):
- **same-host fast-path**: under `external-aggressive` and `max-speed`, when neutral isolation is not required, allow per-invocation explicit self-provider override. Keep the stored file canonical; this is a routing rule, not a persisted key.
- **overflow means spill, not serialize**: under `external-aggressive`, internal slot saturation pushes independent eligible lanes into `$external-worker`, `$external-reviewer`, or `$external-brigade` by default.
- **power-mode means hardest-task maximum useful result**: start from the `quality-first` provider-priority profile, then combine `correctness-first` validation density with `external-aggressive` fan-out, while keeping neutral workdirs and production-only `auto` routing so the extra power does not become a hidden project-state or example-provider shortcut.

## Steps

1. **Verify the official Qwen bootstrap first.**
   - Read the project's `QWEN.md`.
   - If `QWEN.md` is missing, stop and tell the user to run Qwen's built-in `/init` first.
   - Treat `/init` as the canonical owner for creating or refreshing `QWEN.md`.

2. **Read current overlay state.**
   - Read `.qwen/.agents-mode.yaml` first.
   - If it is missing, read legacy `.qwen/.agents-mode` as compatibility input only.
   - If both local files are missing, fall back through pack-local global `~/.qwen/.agents-mode.yaml`, pack-local global legacy `~/.qwen/.agents-mode`, then the shared cross-pack global `~/.agents-mode.yaml` (alongside `~/.claude.json`), before applying built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale.
   - If either file exists, normalize it to the current canonical format before presenting or trusting any values.
   - Any read of `.qwen/.agents-mode.yaml` that drives a decision should normalize the file to the current canonical format before trusting the flags.
   - If neither local nor global overlay exists, start from the canonical defaults below.
   - Preserve unknown keys when updating an existing file.

3. **Read the canonical operator reference when it is available.**
   - If the current repository includes `docs/agents-mode-reference.md`, read it and use it as the authoritative value-by-value reference.
   - If that document is not present in the installed runtime, rely on this skill's canonical schema and rules below instead of inventing extra Qwen-only keys.

4. **Select a preset (optional).**
   - Ask the user if they want to start from a preset: `default`, `absolute-balance`, `external-aggressive`, `correctness-first`, `power-mode`, or `max-speed`.
   - If the user picks a preset, apply its key expansion from the table above as the starting values.
   - After applying a preset, ask whether to write that preset as-is or fine-tune individual keys first.
   - If the user says `use the preset`, `preset only`, `apply as-is`, or otherwise declines manual tweaking, skip the key-by-key overlay walkthrough and carry the preset-expanded values straight to confirmation.
   - If the user says `custom` or skips this step, start from the `default` baseline.
   - The preset name is NOT persisted; only the expanded canonical keys are written.

5. **Configure the shared routing overlay.**
   - Run this step only when the user started from `custom`, skipped preset selection, or explicitly asked to fine-tune after selecting a preset.
   - Walk through these keys one at a time:
     - `consultantMode`
     - `delegationMode`
     - `parallelMode`
     - `mcpMode`
     - `preferExternalWorker`
     - `preferExternalReviewer`
     - `externalProvider`
     - `externalPriorityProfile`
     - `reserveResolver`
     - `externalPriorityProfiles`
     - `externalOpinionCounts`
     - `externalCodexWorkdirMode`
     - `externalClaudeWorkdirMode`
     - `externalModelMode`
     - `externalCodexProfile`
   - Use existing values when present, the preset-expanded value if one was selected, or otherwise default to:
     - `consultantMode: disabled`
     - `delegationMode: auto`
     - `parallelMode: auto`
     - `mcpMode: auto`
     - `preferExternalWorker: false`
     - `preferExternalReviewer: false`
     - `externalProvider: auto`
     - `externalPriorityProfile: balanced`
     - `reserveResolver: claude-sonnet`
     - `externalPriorityProfiles.balanced` and `externalPriorityProfiles.quality-first`: current shipped production matrices using `codex | claude` plus advisory/review-only `reserve`
     - `externalOpinionCounts`: `1` for ordinary lanes unless a repo-local policy explicitly asks for more
     - `externalCodexWorkdirMode: neutral`
     - `externalClaudeWorkdirMode: neutral`
     - `externalModelMode: runtime-default`
     - `externalCodexProfile: default`
   - Accept shorthand such as `force`, `external reviewer only`, `balanced profile`, `explicit qwen`, or `pinned top pro`.
   - Do not invent shipped profile names beyond `balanced` and `quality-first`. If the user wants another profile, treat it as repo-local custom data and keep `gemini` / `qwen` out of any profile the user expects to behave as production `auto`.

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
   delegationMode: {value}  # allowed: manual | auto | force; default: auto
   parallelMode: {value}  # allowed: manual | auto | force; default: auto
   mcpMode: {value}  # allowed: auto | force; default: auto
   preferExternalWorker: {value}  # allowed: false | true; default: false
   preferExternalReviewer: {value}  # allowed: false | true; default: false
   externalProvider: {value}  # allowed here: auto | codex | claude | gemini | qwen; default: auto; gemini/qwen are WEAK MODEL / NOT RECOMMENDED example-only routes
   externalPriorityProfile: {value}  # allowed: balanced | quality-first | <repo-local production profile>; default: balanced
   reserveResolver: {value}  # allowed: disabled | claude-sonnet | claude-wrapper | wrapper:<command>; default: claude-sonnet
   externalPriorityProfiles:
     balanced:
       advisory.repo-understanding: [claude, codex, reserve]
       advisory.design-adr: [claude, codex, reserve]
       design.ui-ux-structure: [codex, claude]
       worker.reasoning-constraints: [claude, codex]
       worker.default-implementation: [codex, claude]
       worker.systems-performance-implementation: [claude, codex]
       worker.ui-implementation: [claude, codex]
       worker.visual-graphics-visualization: [claude, codex]
       review.pre-pr: [claude, codex, reserve]
       review.security: [claude, codex, reserve]
       review.performance-architecture: [codex, claude, reserve]
       review.ui-visual-correctness: [codex, claude, reserve]
     quality-first:
       advisory.repo-understanding: [codex, claude, reserve]
       advisory.design-adr: [codex, claude, reserve]
       design.ui-ux-structure: [codex, claude]
       worker.reasoning-constraints: [claude, codex]
       worker.default-implementation: [codex, claude]
       worker.systems-performance-implementation: [codex, claude]
       worker.ui-implementation: [claude, codex]
       worker.visual-graphics-visualization: [claude, codex]
       review.pre-pr: [codex, claude, reserve]
       review.security: [codex, claude, reserve]
       review.performance-architecture: [codex, claude, reserve]
       review.ui-visual-correctness: [codex, claude, reserve]
   externalOpinionCounts:
     advisory.repo-understanding: 1
     advisory.design-adr: 1
     design.ui-ux-structure: 1
     worker.reasoning-constraints: 1
     worker.default-implementation: 1
     worker.systems-performance-implementation: 1
     worker.ui-implementation: 1
     worker.visual-graphics-visualization: 1
     review.pre-pr: 1
     review.security: 1
     review.performance-architecture: 1
     review.ui-visual-correctness: 1
   externalCodexWorkdirMode: {value}  # allowed: neutral | project; default: neutral
   externalClaudeWorkdirMode: {value}  # allowed: neutral | project; default: neutral
   externalModelMode: {value}  # allowed: runtime-default | pinned-top-pro; default: runtime-default
   externalCodexProfile: {value}  # allowed: default | gpt-5.6-sol-xhigh | gpt-5.6-sol-max | gpt-5.6-terra; default: gpt-5.6-sol-xhigh
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

## Terms and Abbreviations

- `agents-mode`: Orchestrarium operator configuration overlay for delegation, external provider routing, MCP use, and parallelism.
- `reserve`: symbolic supplemental read-only candidate for advisory/review lanes only; it is separate from primary providers and not valid for worker or mutating routes.
- `reserveResolver`: scalar `agents-mode` key that binds symbolic `reserve` to a concrete read-only resolver such as `claude-sonnet`, `claude-wrapper`, or `wrapper:<command>`.
- `Gemini`: Google Gemini provider line; here it is explicit example-only and `WEAK MODEL / NOT RECOMMENDED`.
- `MCP`: Model Context Protocol; protocol for exposing tools and resources to agent runtimes.
- `Qwen`: Qwen provider line; here it is explicit example-only and `WEAK MODEL / NOT RECOMMENDED`.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for example-only providers excluded from production `auto` routing.

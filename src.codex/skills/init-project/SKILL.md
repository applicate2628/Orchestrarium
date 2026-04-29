---
name: init-project
description: Configure project policies in AGENTS.md and review or update .agents/.agents-mode.yaml.
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

## Preset expansion table

Presets are init-time shortcuts only. They expand into canonical `agents-mode` keys. The preset name is NOT persisted in the file.

| Key | `default` (safe-init) | `absolute-balance` (everyday center) | `external-aggressive` (aggressive external use) | `correctness-first` (no-time-limit correctness) | `max-speed` (speed-first) |
|---|---|---|---|---|---|
| `consultantMode` | `disabled` | `internal` | `external` | `external` | `disabled` |
| `externalClaudeApiMode` | `auto` | `auto` | `auto` | `auto` | `auto` |
| `delegationMode` | `manual` | `auto` | `force` | `force` | `auto` |
| `parallelMode` | `auto` | `auto` | `force` | `auto` | `force` |
| `mcpMode` | `auto` | `auto` | `auto` | `force` | `auto` |
| `preferExternalWorker` | `false` | `false` | `true` | `true` | `false` |
| `preferExternalReviewer` | `false` | `true` | `true` | `true` | `false` |
| `externalProvider` | `auto` | `auto` | `auto` | `auto` | `auto` |
| `externalPriorityProfile` | `balanced` | `balanced` | `balanced` | `balanced` | `balanced` |
| `externalPriorityProfiles` | shipped as-is | shipped as-is | shipped as-is | shipped as-is | shipped as-is |
| `externalOpinionCounts` | all `1` | all `1` | all `1` | advisory+review lanes `2`, others `1` | all `1` |
| `externalCodexWorkdirMode` | `neutral` | `neutral` | `neutral` | `neutral` | `project` |
| `externalClaudeWorkdirMode` | `neutral` | `neutral` | `neutral` | `neutral` | `project` |
| `externalModelMode` | `runtime-default` | `runtime-default` | `runtime-default` | `pinned-top-pro` | `runtime-default` |
| `externalClaudeProfile` | `opus-max` | `sonnet-high` | `sonnet-high` | `opus-max` | `sonnet-high` |

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

1. **Read current state.**
   - Read the project's root `AGENTS.md` and check whether a `## Project policies` section already exists.
   - Read `.agents/.agents-mode.yaml` first.
   - If it is missing, read legacy `.agents/.agents-mode` as compatibility input only.
   - If both local files are missing, fall back to global `~/.codex/.agents-mode.yaml` and then global legacy `~/.codex/.agents-mode` as compatibility input.
   - If either file exists, normalize it to the current canonical format before presenting or trusting the current values.
   - If any file exists, normalize the effective file to the current canonical format before presenting or trusting the current values.
   - Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file. If the effective config came from the global scope, use it as the starting point for the project-local review instead of pretending there was no prior state.
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

4. **Select a preset (optional).**
    - Ask the user if they want to start from a preset: `default`, `absolute-balance`, `external-aggressive`, `correctness-first`, or `max-speed`.
    - If the user picks a preset, apply its full key expansion from the table above as the starting values.
    - After applying a preset, ask whether to write that preset as-is or fine-tune individual keys first.
    - If the user says `use the preset`, `preset only`, `apply as-is`, or otherwise declines manual tweaking, skip the key-by-key operator-mode walkthrough and carry the preset-expanded values straight to confirmation.
    - If the user says "custom" or skips this step, start from the `default` baseline.
    - The preset name is NOT persisted — only the expanded canonical keys are written.

5. **Configure operator modes.**
   - Run this step only when the user started from `custom`, skipped preset selection, or explicitly asked to fine-tune after selecting a preset.
   - Walk through the canonical `agents-mode` keys one at a time:
     - `consultantMode`
     - `externalClaudeApiMode`
     - `delegationMode`
     - `parallelMode`
     - `mcpMode`
     - `preferExternalWorker`
     - `preferExternalReviewer`
     - `externalProvider`
     - `externalPriorityProfile`
     - `externalCodexWorkdirMode`
     - `externalClaudeWorkdirMode`
     - `externalModelMode`
     - `externalClaudeProfile`
   - Use the existing value when present, the preset-expanded value if one was selected, or otherwise default to:
     - `consultantMode: disabled`
   - `externalClaudeApiMode: auto`
   - `delegationMode: manual`
   - `parallelMode: auto`
     - `mcpMode: auto`
   - `preferExternalWorker: false`
   - `preferExternalReviewer: false`
   - `externalProvider: auto`
   - `externalPriorityProfile: balanced`
   - shipped `externalPriorityProfiles`
   - `externalOpinionCounts` defaulting each documented lane to `1`
   - `externalCodexWorkdirMode: neutral`
   - `externalClaudeWorkdirMode: neutral`
   - `externalModelMode: runtime-default`
   - `externalClaudeProfile: opus-max`
   - Accept shorthand answers such as `force`, `external reviewer only`, `opus`, or `defaults for the rest`.

6. **Confirm the final choices.**
   - Present one summary table for `## Project policies`.
   - Present one summary table for `.agents/.agents-mode.yaml`.
   - Ask for confirmation before writing.

7. **Write `.agents/.agents-mode.yaml`.**
   - Write the canonical file to `.agents/.agents-mode.yaml`.
   - Preserve unknown keys when updating an existing file.
   - Treat comment-free, partial, or older-layout files as legacy input and rewrite them to the current canonical format instead of preserving stale layout.
   - Do not recreate legacy `.agents/.agents-mode`; write the canonical output only to `.agents/.agents-mode.yaml`.
   - Keep one key per line and include inline comments for every canonical scalar key plus every shipped `externalPriorityProfiles` / `externalOpinionCounts` entry.
   - Refresh the shipped `externalPriorityProfiles` and `externalOpinionCounts` blocks to the current pack version while preserving the effective values of known keys and any unknown keys.

   Use this canonical shape:

   ```yaml
   consultantMode: {value}  # allowed: external | internal | disabled; default: disabled
   externalClaudeApiMode: {value}  # controls advisory/review-only claude-secret candidate: disabled | auto | force; default: auto
   delegationMode: {value}  # allowed: manual | auto | force; default: manual
   parallelMode: {value}  # allowed: manual | auto | force; default: auto
   mcpMode: {value}  # allowed: auto | force; default: auto
   preferExternalWorker: {value}  # allowed: false | true; default: false
   preferExternalReviewer: {value}  # allowed: false | true; default: false
   externalProvider: {value}  # allowed here: auto | codex | claude | gemini | qwen; default: auto; gemini/qwen are explicit example-only and not recommended
   externalPriorityProfile: {value}  # allowed: balanced | <repo-local production profile>; default: balanced
   externalPriorityProfiles: {value}  # allowed: structured profile map
   externalOpinionCounts: {value}  # allowed: structured lane-count map
   externalCodexWorkdirMode: {value}  # allowed: neutral | project; default: neutral
   externalClaudeWorkdirMode: {value}  # allowed: neutral | project; default: neutral
   externalModelMode: {value}  # allowed: runtime-default | pinned-top-pro; default: runtime-default
   externalClaudeProfile: {value}  # allowed: sonnet-high | opus-max; default: opus-max
   ```

8. **Write `## Project policies` to `AGENTS.md`.**
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

9. **Confirm completion.**
   - Tell the user the project policies and operator mode file are saved.
   - Mention `$second-opinion` for later consultant toggle changes.

## Rules

- Be concise; the catalog and dispatch contract hold the details.
- Do not invent extra policy keys or extra `agents-mode` keys.
- Preserve unknown keys in `.agents/.agents-mode.yaml` when updating.
- Any read of `.agents/.agents-mode.yaml` that drives a decision should normalize the file to the current canonical format before trusting the flags.
- Any read of the effective Codex overlay that drives a decision should normalize that file to the current canonical format before trusting the flags.
- Any read that drives a decision should prefer local `.agents/.agents-mode.yaml`, then local legacy `.agents/.agents-mode`, then global `~/.codex/.agents-mode.yaml`, then global legacy `~/.codex/.agents-mode`; normalize whichever file supplied the effective config in the same scope and do not recreate any legacy file.
- Do not modify any other section of `AGENTS.md`.
- Treat root `AGENTS.md` as the project-runtime target, not the Orchestrarium monorepo maintenance overlay.

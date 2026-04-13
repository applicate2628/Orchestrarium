---
name: agents-init-project
description: You are guiding the user through project policy configuration for the Claudestrator skill-pack.
disable-model-invocation: true
---
# Initialize Project Policies

You are guiding the user through project policy configuration for the Claudestrator skill-pack.

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

1. **Read current state.**
   - Read `.claude/CLAUDE.md` and check if a `## Project policies` section already exists.
   - Read `.claude/.agents-mode.yaml` first.
   - If it is missing, read legacy `.claude/.agents-mode` as compatibility input only.
   - If either file exists, normalize it to the current canonical format before presenting or trusting the current values.
   - Normalize either input forward into `.claude/.agents-mode.yaml` and do not recreate legacy `.claude/.agents-mode`.
   - If either surface already exists, show the current values and ask whether to keep them, review them, or start fresh.

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

4. **Select a preset (optional).**
   - Ask the user if they want to start from a preset: `default`, `absolute-balance`, `external-aggressive`, `correctness-first`, or `max-speed`.
   - If the user picks a preset, apply its full key expansion from the table above as the starting values.
   - After applying a preset, ask whether to write that preset as-is or fine-tune individual keys first.
   - If the user says `use the preset`, `preset only`, `apply as-is`, or otherwise declines manual tweaking, skip the key-by-key operator-mode walkthrough and carry the preset-expanded values straight to confirmation.
   - If the user says "custom" or skips this step, start from the `default` baseline.
   - The preset name is NOT persisted — only the expanded canonical keys are written.

5. **Configure operator modes.**
   - Run this step only when the user started from `custom`, skipped preset selection, or explicitly asked to fine-tune after selecting a preset.
   - Walk through the canonical Claude-line `agents-mode` keys one at a time:
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
    - Use the existing value when present, the preset-expanded value if one was selected, or otherwise default to:
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
   - `externalProvider: auto` resolves by lane type through the active named priority profile rather than a Claude-line default provider. Explicit `codex`, `claude`, or `gemini` may still be selected when the route is eligible, and documented repo-local visual heuristics may rank Gemini first for image/icon/decorative visual work when that routing remains honest.
   - `externalOpinionCounts` is a same-lane distinct-opinion requirement, not a concurrency cap; use the brigade surface when you need bounded parallel same-provider reuse.
   - Accept shorthand answers such as `force`, `external reviewer only`, or `defaults for the rest`.

6. **Confirm choices.**
   - Present one summary table for `## Project policies`.
   - Present one summary table for `.claude/.agents-mode.yaml`.
   - Ask for confirmation before writing.

7. **Write `.claude/.agents-mode.yaml`.**
   - Write the canonical file to `.claude/.agents-mode.yaml`.
   - Preserve unknown keys when updating an existing file.
   - Treat comment-free, partial, or older-layout files as legacy input and rewrite them to the current canonical format instead of preserving stale layout.
   - Do not recreate legacy `.claude/.agents-mode`; write the canonical output only to `.claude/.agents-mode.yaml`.
   - Keep one key per line and include the inline allowed-values comment for every canonical key.
   - Refresh the shipped `externalPriorityProfiles` and `externalOpinionCounts` blocks to the current pack version while preserving the effective values of known keys and any unknown keys.
   - Do not recreate retired legacy operator-overlay files.

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
   externalClaudeSecretMode: {value}  # allowed when Claude is selected: auto | force
   externalClaudeApiMode: {value}  # allowed when Claude is selected: disabled | auto | force
   ```

8. **Write to CLAUDE.md.** Add or replace the `## Project policies` section in `.claude/CLAUDE.md`. Place it between `## Engineering hygiene` and `## Publication safety`. Use this format:

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
   - Tell the user the policies and operator mode file are saved.
   - Mention `/agents-policies` to view project policies later.
   - Mention `.claude/.agents-mode.yaml` for future operator-mode changes.

## Rules

- Be concise in explanations — the catalog has the details.
- Accept shorthand answers ("tdd", "80", "conventional", "trunk", etc.).
- If the user gives a custom answer that doesn't match an option, record it as-is.
- Do not invent extra `agents-mode` keys beyond the canonical Claude-line schema.
- Preserve unknown keys in `.claude/.agents-mode.yaml` when updating.
- Any read of `.claude/.agents-mode.yaml` that drives a decision should normalize the file to the current canonical format before trusting the flags.
- Any read that drives a decision should prefer `.claude/.agents-mode.yaml`, fall back to legacy `.claude/.agents-mode` only if the canonical file is missing, normalize either input forward into `.claude/.agents-mode.yaml`, and not recreate the legacy file.
- Do not change any other section of CLAUDE.md.

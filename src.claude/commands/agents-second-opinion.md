# Second Opinion

Get an independent second opinion via the consultant agent.

## Steps

0. **Check toggle mode.** Before invoking the consultant:
   - If `$ARGUMENTS` is one of the toggle sub-commands, handle it directly:
    - `enable` → write `consultantMode: external` to `.claude/.agents-mode.yaml`, preserving or initializing `externalClaudeApiMode: auto`, `delegationMode: manual`, `parallelMode: auto`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles`, `externalOpinionCounts` defaulting each documented lane to `1`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, and `externalModelMode: runtime-default`. If the local file does not yet exist, inherit the effective known values from global `~/.claude/.agents-mode.yaml` (or global legacy `~/.claude/.agents-mode`) when available; otherwise initialize those defaults directly. Keep `externalProvider` lane-driven through the active named production priority profile; shipped `auto` stays on `codex | claude`, and any Gemini or Qwen use must stay explicit example-only. Print "Consultant enabled (external-first)." and exit.
    - `internal` → write `consultantMode: internal` to `.claude/.agents-mode.yaml`, preserving `externalClaudeApiMode`, `delegationMode`, `parallelMode`, `mcpMode`, the preference flags, `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalModelMode`. If the local file does not yet exist, inherit the effective known values from global `~/.claude/.agents-mode.yaml` (or global legacy `~/.claude/.agents-mode`) when available; otherwise initialize `externalClaudeApiMode: auto`, `delegationMode: manual`, `parallelMode: auto`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles`, `externalOpinionCounts` defaulting each documented lane to `1`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, and `externalModelMode: runtime-default`. Keep `externalProvider` lane-driven through the active named production priority profile; shipped `auto` stays on `codex | claude`, and any Gemini or Qwen use must stay explicit example-only. Print "Consultant set to internal-only." and exit.
    - `disable` → write `consultantMode: disabled` to `.claude/.agents-mode.yaml`, preserving `externalClaudeApiMode`, `delegationMode`, `parallelMode`, `mcpMode`, the preference flags, `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalModelMode`. If the local file does not yet exist, inherit the effective known values from global `~/.claude/.agents-mode.yaml` (or global legacy `~/.claude/.agents-mode`) when available; otherwise initialize `externalClaudeApiMode: auto`, `delegationMode: manual`, `parallelMode: auto`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles`, `externalOpinionCounts` defaulting each documented lane to `1`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, and `externalModelMode: runtime-default`. Keep `externalProvider` lane-driven through the active named production priority profile; shipped `auto` stays on `codex | claude`, and any Gemini or Qwen use must stay explicit example-only. Print "Consultant disabled." and exit.
    - `status` → read and normalize `.claude/.agents-mode.yaml`. If local `.claude/.agents-mode.yaml` is absent, continue with local legacy `.claude/.agents-mode`, global `~/.claude/.agents-mode.yaml`, then global legacy `~/.claude/.agents-mode`. If neither local nor global file exists: print "disabled (no file — run `/agents-second-opinion enable` to activate)". Otherwise rewrite the effective file into the current canonical format in the same scope, then print the current consultant mode plus any `externalClaudeApiMode`, `delegationMode`, `parallelMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalModelMode` keys that are present. Exit.
  - If neither local nor global Claude overlay exists: print "Second opinion skipped — consultant disabled. Run `/agents-second-opinion enable` to activate." and exit.
   - If the file contains `consultantMode: disabled`: same notification and exit.
   - Otherwise proceed to step 1.

   When reading, creating, or rewriting `.claude/.agents-mode.yaml`, normalize it to the current canonical format: keep one key per line, restore inline YAML allowed-value comments, refresh the shipped profile/count blocks, preserve effective known values and unknown keys, and drop retired canonical keys. Legacy `.claude/.agents-mode` is compatibility input only and must not be recreated.

1. **Get the question.** Use `$ARGUMENTS` as the question or topic. If empty, ask the user what they want a second opinion on.

2. **Invoke consultant.** Use `subagent_type: consultant`:
   - Pass the question along with relevant context (current file, recent changes, or accepted artifacts)
  - Normalize the effective Claude overlay to the current canonical format before trusting its flags.
  - Resolve in this order: local `.claude/.agents-mode.yaml`, local legacy `.claude/.agents-mode`, global `~/.claude/.agents-mode.yaml`, then global legacy `~/.claude/.agents-mode`.
  - The consultant uses the provider selected by the effective Claude overlay (`externalProvider: auto` resolves by the active named production priority profile and stays on `codex | claude`; explicit `codex`, `claude`, `gemini`, or `qwen` may be selected when the route is eligible, but Gemini and Qwen stay explicit `WEAK MODEL / NOT RECOMMENDED` example-only paths; `externalClaudeApiMode` only controls the supplemental `claude-secret` advisory candidate when the profile order reaches it). `consultantMode: external` stays external-only.

3. **Present the memo.** Display the consultant's advisory memo:
   - Recommended direction
   - Alternatives considered
   - Major tradeoffs
   - Key risks
   - Confidence level
   - Continuation prompt — a ready-to-send second prompt that begins with a direct imperative to continue and names the next concrete action

4. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/advisory.md`
   - Log to `.reports/YYYY-MM/report(consultant)-YYYY-MM-DD_HH-MM_topic.md`

## Rules

- **The consultant MUST be invoked via the Agent tool** with `subagent_type: consultant`. Do not role-play the consultant inline.
- Consultant is advisory-only — do not treat the memo as a blocking gate.
- The toggle file is shared with the external dispatch contract, so never rewrite it into a mode-only shape.
- Do not modify any files.
- If the memo identifies a real blocker, recommend the proper specialist role to handle it.

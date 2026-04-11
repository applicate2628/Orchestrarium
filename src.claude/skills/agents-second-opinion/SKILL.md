---
name: agents-second-opinion
description: Get an independent second opinion via the consultant agent.
disable-model-invocation: true
---
# Second Opinion

Get an independent second opinion via the consultant agent.

## Steps

0. **Check toggle mode.** Before invoking the consultant:
   - If `$ARGUMENTS` is one of the toggle sub-commands, handle it directly:
     - `enable` → write `consultantMode: external` to `.claude/.agents-mode`, preserving or initializing `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles`, `externalOpinionCounts` defaulting each documented lane to `1`, `externalClaudeSecretMode: auto`, and `externalClaudeApiMode: auto`. If the file does not yet exist, initialize those defaults directly. Keep `externalProvider` lane-driven through the active named priority profile; the active profile or documented repo-local visual heuristic may rank Gemini first for image/icon/decorative visual work when that routing remains honest. Print "Consultant enabled (external-first)." and exit.
     - `internal` → write `consultantMode: internal` to `.claude/.agents-mode`, preserving `delegationMode`, `mcpMode`, the preference flags, `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalClaudeSecretMode`, and `externalClaudeApiMode`. If the file does not yet exist, initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles`, `externalOpinionCounts` defaulting each documented lane to `1`, `externalClaudeSecretMode: auto`, and `externalClaudeApiMode: auto`. Keep `externalProvider` lane-driven through the active named priority profile; the active profile or documented repo-local visual heuristic may rank Gemini first for image/icon/decorative visual work when that routing remains honest. Print "Consultant set to internal-only." and exit.
     - `disable` → write `consultantMode: disabled` to `.claude/.agents-mode`, preserving `delegationMode`, `mcpMode`, the preference flags, `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalClaudeSecretMode`, and `externalClaudeApiMode`. If the file does not yet exist, initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles`, `externalOpinionCounts` defaulting each documented lane to `1`, `externalClaudeSecretMode: auto`, and `externalClaudeApiMode: auto`. Keep `externalProvider` lane-driven through the active named priority profile; the active profile or documented repo-local visual heuristic may rank Gemini first for image/icon/decorative visual work when that routing remains honest. Print "Consultant disabled." and exit.
     - `status` → read and normalize `.claude/.agents-mode`. If no file: print "disabled (no file — run `/agents-second-opinion enable` to activate)". Otherwise rewrite it into the current canonical format, then print the current consultant mode plus any `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `externalOpinionCounts`, `externalClaudeSecretMode`, and `externalClaudeApiMode` keys that are present. Exit.
   - If `.claude/.agents-mode` does not exist: print "Second opinion skipped — consultant disabled. Run `/agents-second-opinion enable` to activate." and exit.
   - If the file contains `consultantMode: disabled`: same notification and exit.
   - Otherwise proceed to step 1.

   When reading, creating, or rewriting `.claude/.agents-mode`, normalize it to the current canonical format: keep one key per line, restore inline YAML allowed-value comments, refresh the shipped profile/count blocks, preserve effective known values and unknown keys, and drop retired canonical keys.
   `externalOpinionCounts` is a same-lane distinct-opinion requirement, not a concurrency cap; use the brigade surface when you need bounded parallel same-provider reuse.

1. **Get the question.** Use `$ARGUMENTS` as the question or topic. If empty, ask the user what they want a second opinion on.

2. **Invoke consultant.** Use `subagent_type: consultant`:
   - Pass the question along with relevant context (current file, recent changes, or accepted artifacts)
   - Normalize `.claude/.agents-mode` to the current canonical format before trusting its flags.
   - The consultant uses the provider selected by `.claude/.agents-mode` (`externalProvider: auto` resolves by the active named priority profile; explicit `codex`, `claude`, or `gemini` may be selected when the route is eligible; Claude transport knobs apply only when the resolved provider is `claude`). `consultantMode: external` stays external-only.

3. **Present the memo.** Display the consultant's advisory memo:
   - Recommended direction
   - Alternatives considered
   - Major tradeoffs
   - Key risks
   - Confidence level

4. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/advisory.md`
   - Log to `.reports/YYYY-MM/report(consultant)-YYYY-MM-DD_HH-MM_topic.md`

## Rules

- **The consultant MUST be invoked via the Agent tool** with `subagent_type: consultant`. Do not role-play the consultant inline.
- Consultant is advisory-only — do not treat the memo as a blocking gate.
- The toggle file is shared with the external dispatch contract, so never rewrite it into a mode-only shape.
- Do not modify any files.
- If the memo identifies a real blocker, recommend the proper specialist role to handle it.

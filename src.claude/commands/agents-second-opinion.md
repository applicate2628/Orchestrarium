# Second Opinion

Get an independent second opinion via the consultant agent.

## Steps

0. **Check toggle mode.** Before invoking the consultant:
   - If `$ARGUMENTS` is one of the toggle sub-commands, handle it directly:
     - `enable` → write `consultantMode: external` to `.claude/.agents-mode.yaml`, preserving or initializing `externalClaudeApiMode: auto`, `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles`, and `externalOpinionCounts` defaulting each documented lane to `1`. If the file does not yet exist, initialize those defaults directly. Keep `externalProvider` lane-driven through the active named priority profile; the active profile or documented repo-local visual heuristic may rank Gemini first for image/icon/decorative visual work when that routing remains honest. Print "Consultant enabled (external-first)." and exit.
     - `internal` → write `consultantMode: internal` to `.claude/.agents-mode.yaml`, preserving `externalClaudeApiMode`, `delegationMode`, `mcpMode`, the preference flags, `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`. If the file does not yet exist, initialize `externalClaudeApiMode: auto`, `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles`, and `externalOpinionCounts` defaulting each documented lane to `1`. Keep `externalProvider` lane-driven through the active named priority profile; the active profile or documented repo-local visual heuristic may rank Gemini first for image/icon/decorative visual work when that routing remains honest. Print "Consultant set to internal-only." and exit.
     - `disable` → write `consultantMode: disabled` to `.claude/.agents-mode.yaml`, preserving `externalClaudeApiMode`, `delegationMode`, `mcpMode`, the preference flags, `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`. If the file does not yet exist, initialize `externalClaudeApiMode: auto`, `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles`, and `externalOpinionCounts` defaulting each documented lane to `1`. Keep `externalProvider` lane-driven through the active named priority profile; the active profile or documented repo-local visual heuristic may rank Gemini first for image/icon/decorative visual work when that routing remains honest. Print "Consultant disabled." and exit.
     - `status` → read and normalize `.claude/.agents-mode.yaml`. If it is missing, read legacy `.claude/.agents-mode` as compatibility input only, normalize forward into `.claude/.agents-mode.yaml`, and then continue. If neither file exists: print "disabled (no file — run `/agents-second-opinion enable` to activate)". Otherwise rewrite it into the current canonical format, then print the current consultant mode plus any `externalClaudeApiMode`, `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, and `externalOpinionCounts` keys that are present. Exit.
   - If neither `.claude/.agents-mode.yaml` nor legacy `.claude/.agents-mode` exists: print "Second opinion skipped — consultant disabled. Run `/agents-second-opinion enable` to activate." and exit.
   - If the file contains `consultantMode: disabled`: same notification and exit.
   - Otherwise proceed to step 1.

   When reading, creating, or rewriting `.claude/.agents-mode.yaml`, normalize it to the current canonical format: keep one key per line, restore inline YAML allowed-value comments, refresh the shipped profile/count blocks, preserve effective known values and unknown keys, and drop retired canonical keys. Legacy `.claude/.agents-mode` is compatibility input only and must not be recreated.

1. **Get the question.** Use `$ARGUMENTS` as the question or topic. If empty, ask the user what they want a second opinion on.

2. **Invoke consultant.** Use `subagent_type: consultant`:
   - Pass the question along with relevant context (current file, recent changes, or accepted artifacts)
   - Normalize `.claude/.agents-mode.yaml` to the current canonical format before trusting its flags.
   - If the canonical file is missing, read legacy `.claude/.agents-mode` as compatibility input only and normalize it forward into `.claude/.agents-mode.yaml` before trusting the flags.
   - The consultant uses the provider selected by `.claude/.agents-mode.yaml` (`externalProvider: auto` resolves by the active named priority profile; explicit `codex`, `claude`, or `gemini` may be selected when the route is eligible; Claude transport knobs apply only when the resolved provider is `claude`). `consultantMode: external` stays external-only.

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

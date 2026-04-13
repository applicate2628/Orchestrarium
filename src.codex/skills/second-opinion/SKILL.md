---
name: second-opinion
description: Get an independent second opinion via the consultant agent, or manage the consultant toggle state.
---

# Second Opinion

Get an independent advisory memo or manage the consultant toggle.

## Steps

0. **Check for toggle command.** If `$ARGUMENTS` is one of the toggle sub-commands, handle it directly:
   - `enable` → write `consultantMode: external` to `.agents/.agents-mode.yaml` while preserving `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalGeminiWorkdirMode`, `externalModelMode`, `externalGeminiFallbackMode`, `externalClaudeSecretMode`, `externalClaudeApiMode`, and `externalClaudeProfile` when present. If the file does not exist, initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles` and `externalOpinionCounts`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, `externalGeminiWorkdirMode: neutral`, `externalModelMode: runtime-default`, `externalGeminiFallbackMode: auto`, `externalClaudeSecretMode: auto`, `externalClaudeApiMode: auto`, and `externalClaudeProfile: sonnet-high` unless the user explicitly asked for a different Claude profile. The shared provider universe and lane matrix apply; provider-specific workdir defaults remain neutral, and documented repo-local visual heuristics may still prefer Gemini for image/icon/decorative visual lanes when that routing remains honest. Print "Consultant enabled (external-first)." and exit.
   - `internal` → write `consultantMode: internal` to `.agents/.agents-mode.yaml` while preserving `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalGeminiWorkdirMode`, `externalModelMode`, `externalGeminiFallbackMode`, `externalClaudeSecretMode`, `externalClaudeApiMode`, and `externalClaudeProfile` when present. If the file does not exist, initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles` and `externalOpinionCounts`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, `externalGeminiWorkdirMode: neutral`, `externalModelMode: runtime-default`, `externalGeminiFallbackMode: auto`, `externalClaudeSecretMode: auto`, `externalClaudeApiMode: auto`, and `externalClaudeProfile: sonnet-high` unless the user explicitly asked for a different Claude profile. The shared provider universe and lane matrix apply; provider-specific workdir defaults remain neutral, and documented repo-local visual heuristics may still prefer Gemini for image/icon/decorative visual lanes when that routing remains honest. Print "Consultant set to internal-only." and exit.
   - `disable` → write `consultantMode: disabled` to `.agents/.agents-mode.yaml` while preserving `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalGeminiWorkdirMode`, `externalModelMode`, `externalGeminiFallbackMode`, `externalClaudeSecretMode`, `externalClaudeApiMode`, and `externalClaudeProfile` when present. If the file does not exist, initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles` and `externalOpinionCounts`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, `externalGeminiWorkdirMode: neutral`, `externalModelMode: runtime-default`, `externalGeminiFallbackMode: auto`, `externalClaudeSecretMode: auto`, `externalClaudeApiMode: auto`, and `externalClaudeProfile: sonnet-high` unless the user explicitly asked for a different Claude profile. The shared provider universe and lane matrix apply; provider-specific workdir defaults remain neutral, and documented repo-local visual heuristics may still prefer Gemini for image/icon/decorative visual lanes when that routing remains honest. Print "Consultant disabled." and exit.
   - `status` → read and normalize `.agents/.agents-mode.yaml` first. If it is missing, read legacy `.agents/.agents-mode` as compatibility input only, normalize forward into `.agents/.agents-mode.yaml`, and then continue. If neither file exists: print "disabled (no file — run `/second-opinion enable` to activate)". Otherwise rewrite it into the current canonical format, then print `consultantMode`, `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalGeminiWorkdirMode`, `externalModelMode`, `externalGeminiFallbackMode`, `externalClaudeSecretMode`, `externalClaudeApiMode`, and `externalClaudeProfile` when it is present. Exit.
   - If `$ARGUMENTS` is not a toggle command, proceed to step 1.

   When reading, creating, or rewriting `.agents/.agents-mode.yaml`, normalize it to the current canonical format: keep one key per line, restore inline YAML allowed-value comments, refresh the shipped profile/count blocks, preserve effective known values and unknown keys, and drop retired canonical keys. Legacy `.agents/.agents-mode` is compatibility input only and must not be recreated.

1. **Check toggle state.** Read `.agents/.agents-mode.yaml` first:
   - If it is missing, read legacy `.agents/.agents-mode` as compatibility input only and normalize it forward into `.agents/.agents-mode.yaml`.
   - If the file does not exist: print "disabled (no file — run `/second-opinion enable` to activate)" and exit.
   - If the file exists, normalize it to the current canonical format before evaluating any flags.
   - If `consultantMode: disabled`: print "Consultant is disabled. Run `/second-opinion enable` first." and exit.
   - If `consultantMode: external` / `consultantMode: internal`: proceed.
   - Preserve `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalGeminiWorkdirMode`, `externalModelMode`, `externalGeminiFallbackMode`, `externalClaudeSecretMode`, `externalClaudeApiMode`, and `externalClaudeProfile` on any write; do not clobber them back to defaults when changing `consultantMode`.

2. **Get the question.** Use `$ARGUMENTS` as the question or topic. If empty, ask the user what they want a second opinion on.

3. **Invoke consultant.** Use the consultant role:
   - Pass the question along with relevant context (current file, recent changes, or accepted artifacts).
   - The consultant follows its execution paths based on the current toggle mode.

4. **Present the memo.** Display the consultant's advisory memo:
   - Recommended direction
   - Alternatives considered
   - Major tradeoffs
   - Key risks
   - Confidence level
   - Continuation prompt — a ready-to-send second prompt that begins with a direct imperative to continue and names the next concrete action

5. **Save.** Persist per artifact persistence protocol:
   - If the repository defines an active item artifact path, persist the memo there.
   - Log to `.reports/YYYY-MM/report(consultant)-YYYY-MM-DD_HH-MM_topic.md`

## Rules

- Consultant is advisory-only — do not treat the memo as a blocking gate.
- Do not modify any project files (toggle file excluded).
- If the memo identifies a real blocker, recommend the proper specialist role to handle it.
- The consultant toggle is project-local state stored at `.agents/.agents-mode.yaml`, even when the skill pack itself is installed globally.

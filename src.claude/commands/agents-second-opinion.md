# Second Opinion

Get an independent second opinion via the consultant agent.

## Steps

0. **Check toggle mode.** Before invoking the consultant:
   - If `$ARGUMENTS` is one of the toggle sub-commands, handle it directly:
     - `enable` → write `consultantMode: external` to `.claude/.agents-mode`, preserving or initializing `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, and `externalProvider: auto`. If the new file does not exist, read legacy `.claude/.consultant-mode` for migration if available, but do not carry `externalClaudeProfile` into the new file. Print "Consultant enabled (external-first)." and exit.
     - `auto` → write `consultantMode: auto` to `.claude/.agents-mode`, preserving `delegationMode`, `mcpMode`, the preference flags, and `externalProvider`. If the new file does not exist, initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, and `externalProvider: auto`, or migrate those values from legacy `.claude/.consultant-mode` when available. Print "Consultant enabled (external-first with silent fallback)." and exit.
     - `internal` → write `consultantMode: internal` to `.claude/.agents-mode`, preserving `delegationMode`, `mcpMode`, the preference flags, and `externalProvider`. If the new file does not exist, initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, and `externalProvider: auto`, or migrate those values from legacy `.claude/.consultant-mode` when available. Print "Consultant set to internal-only." and exit.
     - `disable` → write `consultantMode: disabled` to `.claude/.agents-mode`, preserving `delegationMode`, `mcpMode`, the preference flags, and `externalProvider`. If the new file does not exist, initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, and `externalProvider: auto`, or migrate those values from legacy `.claude/.consultant-mode` when available. Print "Consultant disabled." and exit.
     - `status` → read `.claude/.agents-mode` first, then fallback to `.claude/.consultant-mode`. If no file: print "disabled (no file — run `/agents-second-opinion enable` to activate)". Otherwise print the current consultant mode plus any `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, and `externalProvider` keys that are present. Exit.
   - If neither `.claude/.agents-mode` nor `.claude/.consultant-mode` exists: print "Second opinion skipped — consultant disabled. Run `/agents-second-opinion enable` to activate." and exit.
   - If the file contains `consultantMode: disabled` or legacy `mode: disabled`: same notification and exit.
   - Otherwise proceed to step 1.

   When creating or rewriting `.claude/.agents-mode`, keep one key per line and include an inline YAML comment that lists the allowed values for that key.

1. **Get the question.** Use `$ARGUMENTS` as the question or topic. If empty, ask the user what they want a second opinion on.

2. **Invoke consultant.** Use `subagent_type: consultant`:
   - Pass the question along with relevant context (current file, recent changes, or accepted artifacts)
   - The consultant uses the provider selected by `.claude/.agents-mode` (`externalProvider: auto` keeps Codex as the Claude-line default) or falls back to the internal subagent only when `consultantMode` allows it

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

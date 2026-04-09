---
name: second-opinion
description: Get an independent second opinion via the consultant agent, or manage the consultant toggle state.
---

# Second Opinion

Get an independent advisory memo or manage the consultant toggle.

## Steps

0. **Check for toggle command.** If `$ARGUMENTS` is one of the toggle sub-commands, handle it directly:
   - `enable` → write `consultantMode: external` to `.agents/.agents-mode` while preserving `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, and `externalClaudeProfile` when present. If the new file does not exist, read legacy `.agents/.consultant-mode` for migration if available; otherwise initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, and `externalClaudeProfile: sonnet-high` unless the user explicitly asked for a different Claude profile. Print "Consultant enabled (external-first)." and exit.
   - `auto` → write `consultantMode: auto` to `.agents/.agents-mode` while preserving `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, and `externalClaudeProfile` when present. If the new file does not exist, read legacy `.agents/.consultant-mode` for migration if available; otherwise initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, and `externalClaudeProfile: sonnet-high` unless the user explicitly asked for a different Claude profile. Print "Consultant enabled (external-first with silent fallback)." and exit.
   - `internal` → write `consultantMode: internal` to `.agents/.agents-mode` while preserving `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, and `externalClaudeProfile` when present. If the new file does not exist, read legacy `.agents/.consultant-mode` for migration if available; otherwise initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, and `externalClaudeProfile: sonnet-high` unless the user explicitly asked for a different Claude profile. Print "Consultant set to internal-only." and exit.
   - `disable` → write `consultantMode: disabled` to `.agents/.agents-mode` while preserving `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, and `externalClaudeProfile` when present. If the new file does not exist, read legacy `.agents/.consultant-mode` for migration if available; otherwise initialize `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, and `externalClaudeProfile: sonnet-high` unless the user explicitly asked for a different Claude profile. Print "Consultant disabled." and exit.
   - `status` → read `.agents/.agents-mode` first, then fallback to legacy `.agents/.consultant-mode`. If no file: print "disabled (no file — run `/second-opinion enable` to activate)". Otherwise print `consultantMode`, `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, and `externalClaudeProfile` when it is present. Exit.
   - If `$ARGUMENTS` is not a toggle command, proceed to step 1.

When creating or rewriting `.agents/.agents-mode`, keep one key per line and include an inline YAML comment that lists the allowed values for that key.

1. **Check toggle state.** Read `.agents/.agents-mode` first, then fallback to legacy `.agents/.consultant-mode`:
   - If the file does not exist: print "disabled (no file — run `/second-opinion enable` to activate)" and exit.
   - If `consultantMode: disabled` (or legacy `mode: disabled`): print "Consultant is disabled. Run `/second-opinion enable` first." and exit.
   - If `consultantMode: external` / `consultantMode: internal` / `consultantMode: auto` (or matching legacy `mode`): proceed.
   - Preserve `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, and `externalClaudeProfile` on any write; do not clobber them back to defaults when changing `consultantMode`.

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
- The consultant toggle is project-local state stored at `.agents/.agents-mode`, even when the skill pack itself is installed globally. Legacy `.agents/.consultant-mode` is fallback-only and should not be newly created.

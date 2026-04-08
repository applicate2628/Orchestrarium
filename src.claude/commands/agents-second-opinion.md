# Second Opinion

Get an independent second opinion via the consultant agent.

## Steps

0. **Check toggle mode.** Before invoking the consultant:
   - If `$ARGUMENTS` is one of the toggle sub-commands, handle it directly:
     - `enable` → write `mode: external` to `.claude/.consultant-mode`. Print "Consultant enabled (external-first)." and exit.
     - `internal` → write `mode: internal` to `.claude/.consultant-mode`. Print "Consultant set to internal-only." and exit.
     - `disable` → write `mode: disabled` to `.claude/.consultant-mode`. Print "Consultant disabled." and exit.
     - `status` → read `.claude/.consultant-mode`. If no file: print "disabled (no file — run `/agents-second-opinion enable` to activate)". Otherwise print the current mode. Exit.
   - If `.claude/.consultant-mode` does not exist: print "Second opinion skipped — consultant disabled. Run `/agents-second-opinion enable` to activate." and exit.
   - If the file contains `mode: disabled`: same notification and exit.
   - Otherwise proceed to step 1.

1. **Get the question.** Use `$ARGUMENTS` as the question or topic. If empty, ask the user what they want a second opinion on.

2. **Invoke consultant.** Use `subagent_type: consultant`:
   - Pass the question along with relevant context (current file, recent changes, or accepted artifacts)
   - The consultant uses Codex by default (if available) or falls back to internal subagent

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
- Do not modify any files.
- If the memo identifies a real blocker, recommend the proper specialist role to handle it.

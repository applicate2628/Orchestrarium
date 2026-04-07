# Consult

Get an independent second opinion via the consultant agent.

## Steps

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

## Rules

- Consultant is advisory-only — do not treat the memo as a blocking gate.
- Do not modify any files.
- If the memo identifies a real blocker, recommend the proper specialist role to handle it.

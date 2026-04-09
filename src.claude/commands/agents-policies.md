# View or Update Project Policies

You are showing or updating project policies for the Claude Code pack.

## Steps

1. **Read current state.** Read `.claude/CLAUDE.md` and find the `## Project policies` section.

2. **If no policies exist:** Tell the user "No project policies configured yet. Run `/agents-init-project` to set them up." and stop.

3. **If policies exist:** Display them in a clean table:

| Policy | Current value |
| --- | --- |
| Testing | ... |
| ... | ... |

4. **Check for arguments.** If the user provided `$ARGUMENTS`:
   - Parse the argument as `<policy-key> <new-value>` (e.g., `testing tdd`, `coverage 80`, `commits conventional`)
   - Read `.claude/agents/contracts/policies-catalog.md` to validate the key and value
   - Update the specific policy line in the `## Project policies` section of CLAUDE.md
   - Confirm the change

5. **If no arguments:** After showing the table, ask "Want to change anything? Specify like: `/agents-policies testing tdd`" and list available policy keys from the catalog.

## Rules

- Only modify the `## Project policies` section — leave everything else untouched.
- Accept shorthand values that match catalog options.
- If the value doesn't match any catalog option, ask the user to confirm the custom value.
- Show a before/after diff for any change.

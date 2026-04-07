# Resume

Resume an interrupted agent chain from its saved state.

## Steps

1. **Find interrupted work.** Check `$ARGUMENTS`:
   - If a slug is given, load that work-item from `work-items/active/`
   - If empty, scan `work-items/active/` for all items. Display each with: slug, template, current stage, last completed agent, next action.
   - If no active work-items found, say "Nothing to resume."

2. **Load state.** Read `status.md` from the selected work-item:
   - Template and orchestrator (main/lead)
   - Current stage and main conv role
   - Completed agents and their results
   - Next action

3. **Validate.** Before resuming:
   - Check that referenced artifacts still exist
   - Check that the codebase hasn't diverged significantly (quick `git log` since `updated` timestamp)
   - If significant changes detected, warn the user and suggest re-running the analyst stage

4. **Resume execution.** Pick up from the next action in `status.md`:
   - For `requiresLead: false` templates — main conversation continues the chain from where it stopped
   - For `requiresLead: true` templates — invoke `$lead` (Agent tool, `subagent_type: lead`) with the full work-item context
   - Launch the next agent as specified in the next action field

5. **Update status.md** after each stage transition, as usual.

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Read-only until the user confirms resumption — do not auto-start agents.
- If the interrupted chain was a bugfix with `status: open` bug file, link back to it.
- If `status.md` is missing or corrupt, offer to reconstruct from available artifacts or start fresh.

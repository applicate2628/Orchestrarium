---
name: agents-resume
description: Resume an interrupted agent chain from its saved state.
disable-model-invocation: true
---
# Resume

Resume an interrupted agent chain from its saved state.

## Steps

1. **Find interrupted work.** Check `$ARGUMENTS`:
   - If a slug is given, load that work-item from `work-items/active/`
   - If empty, scan `work-items/active/` for all items. Display each with: slug, template, current stage, last completed agent, next action.
   - Also scan `work-items/epics/` for active epics and show each epic's roll-up (k/n children done), so a mid-epic resume restores the epic context, not just the single item.
   - For each item, read the optional `Depends-on: <slug>, <slug>` line in its `status.md` and resolve each target across `work-items/active/` + `work-items/archive/` (done-predicate as in `/agents-status`). Show open targets as `blocked-by`, so the resume picture reflects standing blockers, not just the next action.
   - If no active work-items found, say "Nothing to resume."

2. **Load state.** Read `status.md` from the selected work-item:
   - Template and orchestration weight (`orchestration: light | full-lead`; legacy `orchestrator:` values read main→light, lead→full-lead — the main conversation holds Lead either way)
   - Current stage and main conv role
   - Completed agents and their results
   - Next action

3. **Validate.** Before resuming:
   - Check that referenced artifacts still exist
   - Check that the codebase hasn't diverged significantly (quick `git log` since `updated` timestamp)
   - If significant changes detected, warn the user and suggest re-running the analyst stage
   - If the selected item has an open `Depends-on` target (blocked-by is non-empty), warn that it is `blocked` — resuming its implementation while a declared prerequisite work-item is still open ignores a standing dependency edge. Offer to resume the blocking item instead, or proceed only if the user confirms the dependency is no longer real.

4. **Resume execution.** Pick up from the next action in `status.md`:
   - For `requiresLead: false` templates — main conversation continues the chain from where it stopped
   - For `requiresLead: true` templates — the main conversation holds the Lead role (activate the `/lead` skill) and resumes the full lead pipeline directly with the full work-item context — do not spawn `$lead`
   - Launch the next agent as specified in the next action field

5. **Update status.md** after each stage transition, as usual.

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Read-only until the user confirms resumption — do not auto-start agents.
- If the interrupted chain was a bugfix with `status: open` bug file, link back to it.
- If `status.md` is missing or corrupt, offer to reconstruct from available artifacts or start fresh.

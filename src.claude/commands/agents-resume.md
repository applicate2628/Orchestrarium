# Resume

Resume an interrupted agent chain from its saved state.

## Steps

1. **Find interrupted work.** Check `$ARGUMENTS`:
   - If a slug is given, load that work-item from `work-items/active/`
   - If empty, scan `work-items/active/` for all items. Display each with: slug, template, current step, last result, and next action; read agent execution state from the existing ledger as described below.
   - Also scan `work-items/epics/` for active epics and show each epic's roll-up (k/n children done), so a mid-epic resume restores the epic context, not just the single item.
   - For each item, read the optional top-level `Depends-on: <slug>, <slug>` scalar in its current staged `status.md` and resolve each target across physical `work-items/active/`, `work-items/archive/YYYY-MM/`, and `work-items/backlog/` locations (done-predicate as in `/agents-status`; a backlog match is existence, not done). Use a legacy section lookup only through the compatibility fallback below. Show open targets as `blocked-by` — a target that resolves nowhere is ALSO shown as `blocked-by`, never treated as satisfied — so the resume picture reflects standing blockers, not just the next action. Treat `work-items/index.md` as a compatibility snapshot only.
   - If no active work-items found, say "Nothing to resume."

2. **Load state.** Read `status.md` from the selected work-item:
   - For a current staged record, read `template` and `status` from frontmatter plus the top-level `Task`, `Current step`, `Last result`, and `Next action` scalars. For a current quick-fix record, read the same four recovery facts from its list items.
   - Read `agent-runs.jsonl` for launched/running/terminal roles, completed results, and model/effort only when reported; do not require an Active agents table or infer absent values.
   - Legacy sectioned fallback: only when the record is neither current staged nor quick-fix, read the old Current state, Active agents, Completed agents, and orchestration fields. This may maintain the existing legacy record; it does not make those fields current requirements.
   - Read optional top-level relations such as `Depends-on:` when present; none is mandatory.

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

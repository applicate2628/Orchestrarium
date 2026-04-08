# Project Status

Show a compact status dashboard for the current project.

## Steps

1. **Active work-items.** Check if `work-items/active/` exists and contains subdirectories. For each one, read `status.md` and display:
   - Slug, template, orchestrator (main/lead)
   - Current stage and main conv role (orchestrating/waiting/reviewing/idle)
   - Active agents (role + status) — if any are running
   - Last completed agent and its result
   - Next action
   If no active work-items, say "No active chains."

2. **Project policies.** Read `.claude/CLAUDE.md` and check for `## Project policies` section.
   - If present, list each configured policy (key: value).
   - If absent, say: "No project policies configured. Run `/agents-init-project` to set up."

3. **Open bugs.** Check if `work-items/bugs/` exists. Find all `.md` files with `status: open` in their frontmatter. Display count and list (severity, filename, first line of Description). Group by severity (high first). If none, say "No open bugs."

4. **Open performance issues.** Check if `work-items/performance/` exists. Find all `.md` files with `status: open` in their frontmatter. Display count and list (severity, filename, metric, budget vs actual). Group by severity (high first). If none, say "No open performance issues."

5. **Recent reports.** Check if `.reports/` exists. Find the two most recent subdirectories (by name, format `YYYY-MM`), then list the 5 most recent `.md` files across them. Display filename and first heading. If none, say "No reports."

6. **Recent plans.** Check if `.plans/` exists. Same logic — two most recent month dirs, 5 most recent `.md` files. Display filename and first heading. If none, say "No plans."

7. **Skill-pack summary.** Count and display in one line:
   - Number of role files in `.claude/agents/*.md`
   - Number of team templates in `.claude/agents/team-templates/*.json`
   - Number of skills in `.claude/commands/*.md`

8. **Format.** Display as a compact dashboard:

```text
=== Claudestrator Status ===

Active chains: <count or "none">
  <slug> — <template> (orchestrator: <main|lead>)
    Stage: <current> | Main conv: <role>
    Active agents: <role> (running), <role> (running)
    Last completed: <role> → <PASS|REVISE|BLOCKED>
    Next: <action>

Policies: <configured | not configured>
  <key>: <value> (one per line, if configured)

Open bugs: <count or "none">
  [high] <filename> — <description first line>
  [medium] <filename> — <description first line>

Performance issues: <count or "none">
  [high] <filename> — <metric>: <actual> (budget: <budget>)
  [medium] <filename> — <metric>: <actual> (budget: <budget>)

Recent reports:
  <filename> — <first heading>
  ...

Recent plans:
  <filename> — <first heading>
  ...

Pack: <N> roles · <N> templates · <N> skills
```

## Rules

- Read-only. Do not modify any files.
- Keep output concise — this is a glance, not a report.
- If a directory or file doesn't exist, report its absence gracefully, don't error.

---
name: agents-status
description: Show a compact status dashboard for the current project.
disable-model-invocation: true
---
# Project Status

Show a compact status dashboard for the current project.

## Steps

1. **Active work-items.** Check if `work-items/active/` exists and contains subdirectories. For each one, read `status.md` and display:
   - Slug, template, orchestration weight (light/full-lead; legacy `orchestrator:` values read main→light, lead→full-lead)
   - Current stage and main conv role (orchestrating/waiting/reviewing/idle)
   - Active agents (role + status) — if any are running
   - Last completed agent and its result
   - Priority (if the `## Current state` block has a `Priority: high | medium | low` line): render it as `prio:high` / `prio:medium` / `prio:low` — NOT a bare `[high]` — so it never collides with the bug/perf severity `[high]` brackets elsewhere on the dashboard
   - Next action
   - Blocked-by (if any): the item's open `Depends-on` targets — see the Dependencies sub-bullet
   If no active work-items, say "No active chains."
   - **Epics.** Also check `work-items/epics/` for epic `.md` files. For each, read `status:` and `## Children`, then derive k/n done by resolving each child slug across `work-items/active/` + `work-items/archive/` (a child counts as done if it lives under `archive/`, has a `closure.md`, or its `status.md` has a bare done-state line — the same predicate as `check-work-items-archival-stop.py`). Show `Epic | goal | k/n done | status`; flag any epic at `ready-to-close (n/n)` and any `Epic:` value with no matching epic file. If no epics, say "No epics."
   - **Dependencies.** For each active item, read the optional `Depends-on: <slug>, <slug>` line in its `status.md` `## Current state` block. Resolve each target slug across `work-items/active/` + `work-items/archive/` using the SAME done-predicate as the Epics roll-up. Derive: `blocked-by` = the item's targets that are NOT done (an item with ≥1 open target is `blocked`); `ready-set` = active items whose every target is done (or which have none). Flag a **dangling** `Depends-on` (a target slug matching no item in `active/` or `archive/` — note bugs/epics/decisions are NOT valid targets, only work-items). Do NOT run cycle detection (out of MVP scope — cycle-freedom is a `$lead` authoring rule). Show the blocked count and the ready-set; if every item is ready, say "No blockers."
   - **Backlog.** Read the `## Backlog` section of `work-items/index.md` (items admitted by `$product-manager` but not yet started — the holding area between roadmap admission and active delivery, distinct from Active and Archived). For each backlog row, show slug + priority + one-liner. If the section is absent or empty, say "Backlog empty."

2. **Project policies.** Read `.claude/CLAUDE.md` and check for `## Project policies` section.
   - If present, list each configured policy (key: value).
   - If absent, say: "No project policies configured. Run `/agents-init-project` to set up."

3. **Open bugs.** Check if `work-items/bugs/` exists. Find all `.md` files with `status: open` in their frontmatter. Display count and list (severity, filename, first line of Description). Group by severity (high first). If none, say "No open bugs."

4. **Open performance issues.** Check if `work-items/performance/` exists. Find all `.md` files with `status: open` in their frontmatter. Display count and list (severity, filename, metric, budget vs actual). Group by severity (high first). If none, say "No open performance issues."

5. **Open decisions.** Check if `work-items/decisions/` exists. Each file is a flat `<date>-<slug>.md` with bug-style list-item frontmatter (`- id:`, `- status: proposed | accepted | dropped | superseded | reverted`, `- decided-by:`, `- context:`, `- supersedes:`, `- superseded-by:`). Show every decision whose `- status:` is `proposed` (awaiting acceptance) with its id and `## Decision` first line, plus a one-line count of `accepted`. (`dropped`/`superseded`/`reverted` are terminal/history — do not list them by default.) The decision status enum is INDEPENDENT of the work-item done-predicate — decisions are never "closed" by it. If none, say "No decisions."

6. **Open lessons.** Check if `work-items/lessons/` exists. Each file is a flat `<date>-<slug>.md` with bug-style list-item frontmatter (`- id:`, `- status: open | applied | dropped | archived`, `- source:`, `- category:`). Show every lesson whose `- status:` is `open` (captured, not yet acted on) with its id and `## Lesson` first line, plus the count. (`applied` is a non-open history state that can still move to `archived`; `dropped`/`archived` are terminal — none are listed by default.) The lesson status enum is INDEPENDENT of the work-item done-predicate. If none, say "No open lessons."

7. **Recent reports.** Check if `.reports/` exists. Find the two most recent subdirectories (by name, format `YYYY-MM`), then list the 5 most recent `.md` files across them. Display filename and first heading. If none, say "No reports."

8. **Recent plans.** Check if `.plans/` exists. Same logic — two most recent month dirs, 5 most recent `.md` files. Display filename and first heading. If none, say "No plans."

9. **Skill-pack summary.** Count and display in one line:
   - Number of role files in `.claude/agents/*.md`
   - Number of team templates in `.claude/agents/team-templates/*.json`
   - Number of skills in `.claude/commands/*.md`

10. **Format.** Display as a compact dashboard:

```text
=== Claude Code Pack Status ===

Active chains: <count or "none">
  <slug> — <template> (orchestration: <light|full-lead>) <prio:high|prio:medium|prio:low, or omit if no Priority>
    Stage: <current> | Main conv: <role>
    Active agents: <role> (running), <role> (running)
    Last completed: <role> → <PASS|REVISE|BLOCKED>
    Blocked-by: <open Depends-on targets, or omit line if none>
    Next: <action>

Dependencies: <blocked count or "no blockers">
  Ready to start: <ready-set slugs, or "none">
  Dangling Depends-on: <slug → no matching item, or omit if none>

Backlog: <count or "empty">
  <slug> — <prio:high|prio:medium|prio:low> — <one-liner>

Policies: <configured | not configured>
  <key>: <value> (one per line, if configured)

Open bugs: <count or "none">
  [high] <filename> — <description first line>
  [medium] <filename> — <description first line>

Decisions: <proposed count or "none">
  [proposed] <id> — <decision first line>
  (accepted: <count>)

Open lessons: <count or "none">
  [open] <id> — <lesson first line>

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

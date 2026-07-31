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
   - **Epics.** Also check `work-items/epics/` for epic `.md` files. For each, read `status:` and `## Children`, then derive k/n done by resolving each child slug across `work-items/active/` + `work-items/archive/`; only a unique archive location counts as done. Active status or closure text records evidence but does not terminalize the child. Show `Epic | goal | k/n done | status`; flag any epic at `ready-to-close (n/n)` and any `Epic:` value with no matching epic file. If no epics, say "No epics."
   - **Dependencies.** For each active item, read the optional `Depends-on: <slug>, <slug>` line in its `status.md` `## Current state` block. Resolve each target slug across THREE locations — `work-items/active/`, `work-items/archive/`, and the `## Backlog` *section* of `work-items/index.md` (an admitted-but-not-started item; not a `work-items/backlog/` directory) — using the SAME done-predicate as the Epics roll-up for completion (a backlog match is existence only: an admitted item is never `done`). Derive: `blocked-by` = the item's targets that are NOT done; `ready-set` = active items whose every target is done (or which have none). Flag a **dangling** `Depends-on` (a target slug that resolves in none of the three locations — note bugs/epics/decisions are NOT valid targets, only work-items) — and state explicitly: a dangling target is ALSO folded into `blocked-by`, never treated as satisfied, so `dangling` and `blocked` are NOT mutually exclusive (an unresolvable dependency is not evidence of readiness). Do NOT run cycle detection (out of MVP scope — cycle-freedom is a `$lead` authoring rule). Show the blocked count and the ready-set; if every item is ready, say "No blockers."
   - **Backlog.** Read the `## Backlog` section of `work-items/index.md` (items admitted by `$product-manager` but not yet started — the holding area between roadmap admission and active delivery, distinct from Active and Archived). For each backlog row, show slug + priority + one-liner. If the section is absent or empty, say "Backlog empty."

2. **Project policies.** Read `.claude/CLAUDE.md` and check for `## Project policies` section.
   - If present, list each configured policy (key: value).
   - If absent, say: "No project policies configured. Run `/agents-init-project` to set up."

3. **Open bugs.** Check if `work-items/bugs/` exists. Find all `.md` files with `status: open` in their frontmatter. Display count and list (severity, filename, first line of Description). Group by severity (high first). If none, say "No open bugs."

4. **Open performance issues.** Check if `work-items/performance/` exists. Find all `.md` files with `status: open` in their frontmatter. Display count and list (severity, filename, metric, budget vs actual). Group by severity (high first). If none, say "No open performance issues."

5. **Open decisions.** Check if `work-items/decisions/` exists. Each file is a flat `<date>-<slug>.md` with bug-style list-item frontmatter (`- id:`, `- status: proposed | accepted | dropped | superseded | reverted`, `- decided-by:`, `- context:`, `- supersedes:`, `- superseded-by:`). Show every decision whose `- status:` is `proposed` (awaiting acceptance) with its id and `## Decision` first line, plus a one-line count of `accepted`. (`dropped`/`superseded`/`reverted` are terminal/history — do not list them by default.) The decision status enum is INDEPENDENT of the work-item done-predicate — decisions are never "closed" by it. If none, say "No decisions."

6. **Reserved PM admissions.** Scan the three live cross-cutting registries — `work-items/decisions/`, `work-items/epics/`, and `work-items/bugs/` — for artifacts that reserve a `$product-manager` admission or acceptance that has not yet fired, so a scheduled PM call cannot stall unseen. Flag an artifact ONLY when BOTH signals hold:
   - **(A) PM-admission-owner signal.** On a single line OR two adjacent lines, the body co-locates a `$product-manager` / `product-manager` token with an admission/acceptance action stem from the fixed set `{ admit, admitted, admitting, admission, accept, acceptance, intake, re-intake, pending, call }`. The co-location is what separates a *reserved admission* from a mere role-noun mention — a line that only names `product-manager` as a role, with no admission stem nearby, does NOT qualify.
   - **(B) not-yet-admitted state.** Read the state from the artifact's authoritative frontmatter `status:` field ONLY — the `status:` (or list-item `- status:`) key line in the leading frontmatter block — never a `status:` substring appearing elsewhere in the body (a stale body line that still says "status: proposed" does not count). Per registry: `decisions/*` flags on `status: proposed` (terminal `accepted` / `dropped` / `superseded` / `reverted` are excluded); `epics/*` flags on `status: active` (terminal `closed` excluded); `bugs/*` flags on `status: open` (terminal `fixed` / `resolved` / `closed` / `superseded` excluded).
   Scope: only these three live registries. Exclude `work-items/archive/**` (terminal by location) and the `## Backlog` items in `index.md` (already admitted — they are PM's output, not a reserved call). This flag is a STRICT SUBSET of the step-5 proposed-decisions list — it surfaces only the PM-owned ones, plus the epic and bug analogues, never all `proposed` decisions. When the flagged count is greater than zero, list the flagged artifacts and then append exactly ONE dispatch-offer line (see Format). The offer is presentation only: the command dispatches nothing and modifies no file. If the operator confirms, the MAIN conversation (not this command) dispatches `subagent_type: product-manager` with the flagged artifact(s) as the admission input; the operator may instead admit directly (the `OR direct human decision` bypass stays intact) or decline. If none match, say "Reserved PM admissions: none".

7. **Open lessons.** Check if `work-items/lessons/` exists. Each file is a flat `<date>-<slug>.md` with bug-style list-item frontmatter (`- id:`, `- status: open | applied | dropped | archived`, `- source:`, `- category:`). Show every lesson whose `- status:` is `open` (captured, not yet acted on) with its id and `## Lesson` first line, plus the count. (`applied` is a non-open history state that can still move to `archived`; `dropped`/`archived` are terminal — none are listed by default.) The lesson status enum is INDEPENDENT of the work-item done-predicate. If none, say "No open lessons."

8. **Recent reports.** Check if `.reports/` exists. Find the two most recent subdirectories (by name, format `YYYY-MM`), then list the 5 most recent `.md` files across them. Display filename and first heading. If none, say "No reports."

9. **Recent plans.** Check if `.plans/` exists. Same logic — two most recent month dirs, 5 most recent `.md` files. Display filename and first heading. If none, say "No plans."

10. **Skill-pack summary.** Count and display in one line:
   - Number of role files in `.claude/agents/*.md`
   - Number of team templates in `.claude/agents/team-templates/*.json`
   - Number of skills in `.claude/commands/*.md`

11. **Format.** Display as a compact dashboard:

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

Reserved PM admissions: <count or "none">
  [decision] <id> — proposed, acceptance reserved for $product-manager
  [epic]     <slug> — <active|parked>, admission reserved for $product-manager
  [bug]      <filename> — open, admission reserved for $product-manager
  → <count> reserved $product-manager admission(s) have not fired. Dispatch $product-manager to admit/accept them now? (I will not dispatch or modify any file without your confirmation.)

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
- The reserved-PM-admission section is presentation only: the command flags reserved `$product-manager` admissions and may print the single dispatch-offer line, but it never dispatches a subagent and never modifies any file without explicit operator confirmation.
- Keep output concise — this is a glance, not a report.
- If a directory or file doesn't exist, report its absence gracefully, don't error.

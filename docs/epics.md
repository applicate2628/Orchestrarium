# Epics

An **epic** groups multiple work-items under one goal or milestone — the agile
Epic -> Story -> Task hierarchy mapped onto Orchestrarium's file-based task
memory: **epic -> work-item (story) -> phase (task)**.

Epics are local task memory: `work-items/` is gitignored, so the epic data lives
on your machine; only the rules (in the role files and `CLAUDE.md` / `AGENTS.md`)
are committed.

## Where an epic lives

A flat single file `work-items/epics/<date>-<slug>.md` — the same flat shape as
the existing `work-items/bugs/` registry (not a folder-per-item):

```
---
status: active | closed
epic-id: <date>-<slug>
owner: $lead
admission-source: $product-manager roadmap package / direct human decision
milestone: <one-liner>
---
# Epic: <title>

## Goal
<one-line epic intent>

## Children
- <child-work-item-slug> (active | closed)
- ...

## Closure          (only when status: closed)
Closed: <YYYY-MM-DD>
<outcome, residual risk>
## Retrospective    (optional; What went well / What didn't / Lessons filed in work-items/lessons/ by id)
```

## Linking work-items to an epic

Each child work-item declares its parent with ONE bare line in its `status.md`:

```
Epic: <epic-slug>
```

`Epic:` is single-valued — a work-item belongs to at most one epic.

## Roll-up (derived, never stored)

Epic progress is derived live, never kept as a maintained cache (a cache
drifts). A child is **done** iff its `status.md` carries a bare done-state line
(`status:`/`state:`/`stage:`/`outcome:` whose value begins
`closed|done|complete|completed|archived` — the same predicate the
work-items-archival hook uses), OR it lives under `work-items/archive/`, OR it
has a `closure.md`. Each child slug is resolved across BOTH `work-items/active/`
and `work-items/archive/` (the slug is stable across the close-move). Roll-up:
all done -> `ready-to-close (n/n)`; some -> `in-progress (k/n)`; none -> `open`.
`/agents-status` and `/agents-resume` compute and show it.

## Lifecycle + roles

- `$product-manager` **admits** the epic. The Coherence gate is the epic test:
  an epic must name the shared goal, contract, or mechanism that makes its
  members one unit of work. The PM also bounds the scope so members do not creep
  without re-admission.
- `$lead` **links** children (stamps each child `Epic: <slug>`), keeps the local
  `work-items/index.md` `## Epics` row current, and **closes** the epic
  (`status: closed` + `## Closure`) ONLY when ALL children are closed AND the
  epic goal is met.
- `$knowledge-archivist` handles epic archive moves / local index sync (its
  non-semantic hygiene lane).

### Edge cases
- A 0-child epic rolls up as `open/empty`, never `ready-to-close`.
- Work-items without an epic are valid — they simply omit the `Epic:` line.
- Reopening a child of a closed epic MUST reopen the epic (`status: active`).
- An `Epic:` value with no matching epic file is a dangling link — flag and fix.

## Known limitation

The work-items-archival Stop hook now ALSO scans `work-items/epics/` (Batch B):
at turn end it flags a ready-to-close epic (every child done but the epic still
`status: active`) and a stale-closed epic (`status: closed` but a child is not
done), the same way it flags an unarchived work-item — subagent-safe (skips on
`agent_id`) and failing open when `work-items/epics/` is absent. Still
governance-only: nothing verifies the epic's `## Goal` is actually met (only that
the children are closed), and a child line written without the documented
`(active|closed)` marker is ignored by the scan. Full role rules: `lead.md` / the
lead skill `## Epics`.

## Terms and Abbreviations

- **Epic**: an initiative grouping several work-items toward one goal/milestone.
- **Work-item**: the delivery unit (a "story") — a folder under `work-items/active/`.
- **Phase**: a task within a work-item's plan, produced by `$planner`.
- **Roll-up**: an epic's derived progress (k of n children done) over its members.
- **Coherence gate**: the `$product-manager` admission test that a set of work is
  one coherent unit (defined in `product-manager.md`).

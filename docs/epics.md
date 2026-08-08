# Epics

An **epic** groups multiple work-items under one goal or milestone — the agile
Epic -> Story -> Task hierarchy mapped onto Orchestrarium's file-based task
memory: **epic -> work-item (story) -> phase (task)**.

Epics are local task memory: `work-items/` is gitignored, so the epic data lives
on your machine; only the rules (in the role files and `CLAUDE.md` / `AGENTS.md`)
are committed.

## Where an epic lives

Location is part of the lifecycle state:

- active: `work-items/epics/<date>-<slug>.md`;
- closed: `work-items/epics/archive/<YYYY-MM>/<date>-<slug>.md`, where the
  archive month comes from the `Closed: <YYYY-MM-DD>` line.

Each epic remains one flat file (not a folder-per-item). A slug must resolve to
exactly one location; a copy in both locations or in two archive months is an
invalid duplicate, never a reason to select the newest file.

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
drifts). A child is **done** only when its slug resolves uniquely under
`work-items/archive/`; an active status line or `closure.md` records evidence
but does not make the child terminal. Each child slug is resolved across BOTH
`work-items/active/` and `work-items/archive/` (the slug is stable across the
close-move). Roll-up:
all done -> `ready-to-close (n/n)`; some -> `in-progress (k/n)`; none -> `open`.
`/agents-status` and `/agents-resume` compute and show it.

## Lifecycle + roles

- `$product-manager` **admits** the epic. The Coherence gate is the epic test:
  an epic must name the shared goal, contract, or mechanism that makes its
  members one unit of work. The PM also bounds the scope so members do not creep
  without re-admission.
- When a roadmap decision package names multiple related work-items, a shared
  milestone, or one mechanism split across several items, it must either admit
  an epic or record `No-epic rationale: <why these remain standalone>`.
- `$lead` **links** children (stamps each child `Epic: <slug>`), derives the
  roll-up from physical child locations, and **closes** the epic
  (`status: closed` + `## Closure`) ONLY when ALL children are closed AND the
  epic goal is met.
- `$knowledge-archivist` then moves that same file to
  `work-items/epics/archive/<YYYY-MM>/<slug>.md`, reconciles physical lifecycle
  locations, regenerates `work-items/README.md`, and verifies that the slug has
  exactly one location.

### Edge cases
- A 0-child epic rolls up as `open/empty`, never `ready-to-close`.
- Work-items without an epic are valid — they simply omit the `Epic:` line.
- Reopening a child of a closed epic MUST move the epic back to
  `work-items/epics/<slug>.md` and set `status: active` in the same lifecycle
  operation. An archived active epic is invalid transitional residue.
- An `Epic:` value with no unique active or archived epic file is invalid:
  report missing and duplicate targets distinctly.

## Known limitation

No archival Stop control scans epics. The lifecycle owner and documented state
check reject duplicate locations and missing terminal evidence; whether the
epic `## Goal` is met remains an explicit lead decision. Full role rules:
`skills/lead/SKILL.md` (Claude; `agents/lead.md` activates the main agent and rejects stale dispatch) / the
lead skill (Codex) `## Epics`.

## Physical lifecycle V1

An active epic is `work-items/epics/<slug>.md`; a terminal epic is only
`work-items/epics/archive/YYYY-MM/<slug>.md`. The month comes from strict UTC
`Closed: YYYY-MM-DDTHH:MM:SSZ` evidence. The lifecycle owner rejects duplicate
locations and missing closure evidence; reopening creates a successor rather
than restoring the archived identity. The archival Stop adapter is retired, so
operators use lifecycle validation and the documented state check.

## Terms and Abbreviations

- **Epic**: an initiative grouping several work-items toward one goal/milestone.
- **Work-item**: the delivery unit (a "story") — a folder under `work-items/active/`.
- **Phase**: a task within a work-item's plan, produced by `$planner`.
- **Roll-up**: an epic's derived progress (k of n children done) over its members.
- **Coherence gate**: the `$product-manager` admission test that a set of work is
  one coherent unit (defined in `product-manager.md`).
- **Resolver**: the single lookup owner that distinguishes a unique active epic,
  a unique archived epic, a missing epic, and a duplicate slug.

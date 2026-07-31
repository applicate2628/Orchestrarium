# Lessons registry

A **lessons registry** is a flat, cross-item store of the durable delivery
lessons a project learns — a recurring miss, a wrong assumption, a process gap.
It exists because a lesson learned during delivery that lives only inside a
work-item's `closure.md` or a reviewer's notes is **archived with that item**:
the lesson gets buried under `work-items/archive/` and is no longer queryable
cross-cutting, so the same mistake is repeated. The registry captures the
delivery lesson in-repo so it survives the work-item's archival, in one stable
place separate from the item that produced it.

Lessons are local task memory: `work-items/` is gitignored, so the lesson data
lives on your machine; only the rules (in the role files and `CLAUDE.md` /
`AGENTS.md`) are committed.

## Where a lesson lives

A flat single file `work-items/lessons/<date>-<slug>.md` — the same flat shape
as the `work-items/bugs/` registry (not a folder-per-item), with **bug-style
list-item frontmatter** (`- key:` bullets, NO `---` YAML fences — bugs use
`- status: open`, lessons follow that precedent):

```
- id: <date>-<slug>
- status: open | applied | dropped | archived
- source: <work-item slug | bug slug | review | incident>
- category: process | technical | governance | tooling

# Lesson: <title>

## Lesson
<one-line statement of what was learned>

## Context
<what happened — the work-item, the miss, the surrounding circumstances>

## How to apply
<the concrete next action that would prevent a recurrence>
```

## Status lifecycle

`open` -> `applied` -> `archived`, with `dropped` as the other terminal from
`open`:

- **open** — the lesson was captured but not yet acted on.
- **applied** — the lesson drove a named change (a rule, a checklist item, a
  fix). This is the resolution that closes the loop.
- **dropped** — a lesson considered and judged not worth acting on (keep a
  one-line reason). A dropped lesson leaves the `/agents-status` open-list. This
  is the parity terminal with the decisions registry's `dropped`.
- **archived** — the lesson is no longer relevant (the surface it applied to was
  removed, or it was superseded).

An applied/dropped/archived lesson **stays in the registry** as history; it is
never deleted. This status enum is **independent of** the work-item / epic
done-predicate — lessons are never "closed" by that predicate, so the
retired archival Stop control never acts on them.

## Lifecycle + roles

- A lesson is **captured** by the role that ran the retrospective — the closing
  role (the main conversation, as Lead) or a
  reviewer (`$qa-engineer` or another reviewer) when they spot a recurring miss.
- The **semantic status transitions** (`open -> applied -> archived`, plus `open -> dropped`) are
  owned by the CLOSING role that captured the lesson (the main conversation as
  Lead), escalating to `$product-manager`
  when applying the lesson admits follow-up work.
- `$lead` / `$product-manager` **consult** open lessons when admitting or
  planning similar work, so the same mistake is not repeated.
- `$knowledge-archivist` does ONLY the **non-semantic bookkeeping** (writing the
  stored back-reference id, local index sync) — the same lifecycle/bookkeeping
  split as Epics and Decisions. The archivist does NOT decide a lesson status
  transition.
- **Stale-open accountability:** The main conversation (as Lead) is
  accountable for resolving an `open` lesson that keeps getting surfaced — drive
  it to `applied` (a named change shipped) or `dropped` (a one-line reason).
  Listing it is visibility, not closure.

## Boundary vs personal memory

The lessons registry is **in-repo, project-scoped task memory** — the lesson
DATA is gitignored under `work-items/` like all task memory, and only the rules
are committed. It is NOT the operator's personal global memory
(`~/.claude/.../memory/feedback_*`), which is the operator's PERSONAL
cross-project memory, OUT of repo.

A lesson that generalizes BEYOND this project may ALSO be promoted to the
spine/governance or to personal memory — but that promotion is **additive,
one-directional, and a SEPARATE manual act** outside this registry. The
project-local entry stays the **canonical** project record; promotion copies the
generalized form elsewhere, it does not move or replace the registry entry.
State this so the two stores do not blur.

## Surfacing

On the Claude line, `/agents-status` lists every `open` lesson (a count, plus
each by id and `## Lesson` first line); on the Codex line (no commands) the lead
derives the same open-lessons list live by scanning `work-items/lessons/` for
`status: open`. The operating-model "where to save" surface carries the
`Lesson -> work-items/lessons/<date>-<slug>.md` row (a table on the Claude line,
a prose bullet on the Codex line). Full role rules: `skills/lead/SKILL.md` (Claude; `agents/lead.md` is a fail-closed stub) / the lead skill
(Codex) `## Lessons`, `knowledge-archivist.md` / the archivist skill hygiene lane.

## Known limitation

The lessons registry is **governance-enforced only**. No hook scans
`work-items/lessons/`, so a stale `open` lesson that nobody applies or drops is
not structurally caught — no archival Stop control sees the
registry. This is weaker than the work-item close path, which the hook
backstops. Surfacing the open-list in `/agents-status` is the only standing
prompt to resolve a dangling lesson — and it runs ONLY when you invoke the
command (on the Codex line, when the lead scans the registry); nothing runs in
the background and nothing VALIDATES the registry (no check that a captured
lesson was ever resolved, no check that a `source:` reference exists), so a
stale `open`, an unfiled retrospective lesson, or a wrong reference is caught
only if and when you look.

## Physical lifecycle V1

A terminal lesson moves from `work-items/lessons/` only when its explicit
terminal status, `Terminal-at` strict UTC instant, disposition, and evidence
are present. Its immutable archive target is
`work-items/lessons/archive/YYYY-MM/`; incomplete historical records remain
where they are until a human supplies authoritative facts.

## Terms and Abbreviations

- **Lessons registry**: the flat cross-item store of durable delivery lessons
  under `work-items/lessons/`.
- **open | applied | dropped | archived**: the lesson status enum (independent
  of the work-item done-predicate).
- **applied**: the resolution where a lesson drove a named change (a rule, a
  checklist item, a fix) — the loop-closing transition.
- **dropped**: a lesson considered and judged not worth acting on (keep a
  one-line reason), parity with the decisions registry's `dropped`.
- **retrospective**: the close-step section (`closure.md` `## Retrospective`)
  that produces keep-worthy lessons; the registry is the store, the
  retrospective is the producer.
- **personal global memory**: the operator's out-of-repo cross-project memory
  (`~/.claude/.../memory/feedback_*`) — distinct from this in-repo registry; a
  generalized lesson may be promoted there as a separate manual act.

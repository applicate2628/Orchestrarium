# Decisions registry

A **decision registry** is a flat, cross-item store of the durable architecture
decisions a project makes — the ADR (Architecture Decision Record) idea mapped
onto Orchestrarium's file-based task memory. It exists because an accepted
long-lived decision that lives only inside a work-item's `design.md` is
**archived with that item**: a closed epic's key decisions get buried under
`work-items/archive/` and are no longer queryable cross-cutting. The registry
keeps the decision record in one stable place, separate from the item that
produced it.

Decisions are local task memory: `work-items/` is gitignored, so the decision
data lives on your machine; only the rules (in the role files and `CLAUDE.md` /
`AGENTS.md`) are committed.

## Where a decision lives

A flat single file `work-items/decisions/<date>-<slug>.md` — the same flat shape
as the `work-items/bugs/` registry (not a folder-per-item), with **bug-style
list-item frontmatter** (`- key:` bullets, NO `---` YAML fences — bugs use
`- status: open`, decisions follow that precedent):

```
- id: <date>-<slug>
- status: proposed | accepted | dropped | superseded | reverted
- decided-by: <role or human>
- context: <work-item slug | cross-cutting>
- supersedes: <decision id | none>
- superseded-by: <decision id | none>

# Decision: <title>

## Decision
<one-line statement of what was decided>

## Rationale
<why — the forces, the tradeoff>

## Consequences
<what this commits the project to; follow-on effects>

## Alternatives rejected
<options considered and why they lost>
```

## Status lifecycle

`proposed` -> `accepted` -> `superseded` / `reverted`, with `dropped` as the
other terminal from `proposed`:

- **proposed** — `$architect` authored it; awaiting the acceptance gate.
- **accepted** — promoted after the corresponding architecture-review gate
  passed. Acceptance authority is the `$architecture-reviewer` gate, NOT the
  author and NOT the archivist.
- **dropped** — a proposal considered and declined (keep a one-line reason). A
  dropped proposal leaves the `/agents-status` proposed-list.
- **superseded** — replaced by a newer decision that names it in `supersedes:`.
  The edge is stored **both ways**: when B supersedes A, the same hygiene step
  sets `A.status: superseded` AND `A.superseded-by: B` (mirroring the Epic
  child<->parent two-way link).
- **reverted** — the decision was undone (keep a one-line reason; add a
  `- reverted-by:` only if the revert is itself a registered decision).

A superseded/reverted/dropped decision **stays in the registry** as history; it
is never deleted. This status enum is **independent of** the work-item / epic
done-predicate — decisions are never "closed" by that predicate, so the
retired archival Stop control never acts on them.

## Lifecycle + roles

- `$architect` **authors** a cross-cutting or long-lived decision (one that
  outlives the work-item or constrains others) in the registry as
  `status: proposed`, and the work-item's `design.md` **references it by id**
  instead of duplicating it. Architecture decisions confined to a single item
  stay in that item's `design.md` as before.
- The `$architecture-reviewer` gate **promotes** `proposed -> accepted` as part
  of its normal review — the registry is a durable store, not a new gate.
- `$lead` cites relevant decisions when admitting/planning, and **owns the
  semantic status transitions** (`accepted -> superseded/reverted`, plus the `proposed -> dropped` retirement),
  including setting the two-way `superseded-by` edge.
- `$knowledge-archivist` does ONLY the **non-semantic bookkeeping** (writing the
  stored back-link field, physical-location reconciliation and generated read-model refresh) — the same lifecycle/bookkeeping
  split as Epics. It does not decide a status transition.

## Surfacing

On the Claude line, `/agents-status` lists every `proposed` decision (awaiting
acceptance) by id and `## Decision` first line, plus a count of `accepted`; on
the Codex line (no commands) the lead surfaces the same proposed-list by
scanning the registry. The operating-model "where to save" surface carries the
`Decision -> work-items/decisions/<date>-<slug>.md` row (a table on the Claude
line, a prose bullet on the Codex line). Full role rules: `skills/lead/SKILL.md` (Claude; `agents/lead.md` is a fail-closed stub) / the lead skill (Codex) `## Decisions`,
`architect.md` / the architect skill working rules.

## Known limitation

The decision registry is **governance-enforced only**. No hook scans
`work-items/decisions/`, so a stale `proposed` decision that was never accepted
or dropped, or an `accepted` decision that should have been superseded, is not
structurally caught — no archival Stop control sees the
registry. This is weaker than the work-item close path, which the hook
backstops. Surfacing the proposed-list in `/agents-status` is the only standing
prompt to resolve a dangling proposal — and it runs ONLY when you invoke the
command (on the Codex line, when the lead scans the registry); nothing runs in
the background and nothing VALIDATES the registry (no check that a `superseded-by`
back-link is consistent, no check that a `supersedes:` target exists), so a stale
`proposed`, a half-set supersede edge, or a wrong reference is caught only if and
when you look.

## Physical lifecycle V1

A terminal decision may move from `work-items/decisions/` only through the
lifecycle owner to `work-items/decisions/archive/YYYY-MM/`, after its explicit
terminal status, `Terminal-at` strict UTC instant, rationale, and evidence are
present. Missing historical fields are a human-data decision, not permission
to infer timestamps or rewrite history.

## Terms and Abbreviations

- **Decision registry**: the flat cross-item store of durable architecture
  decisions under `work-items/decisions/`.
- **ADR (Architecture Decision Record)**: an industry pattern of recording one
  architecture decision (context, decision, consequences) as a small versioned
  document. The registry is the ADR idea adapted to Orchestrarium task memory.
- **proposed | accepted | dropped | superseded | reverted**: the decision status
  enum (independent of the work-item done-predicate).
- **supersede**: replace one decision with a newer one; stored as a two-way
  `supersedes:` / `superseded-by:` edge.
- **Acceptance gate**: the `$architecture-reviewer` review that promotes a
  decision from `proposed` to `accepted`.

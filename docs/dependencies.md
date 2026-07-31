# Work-item dependencies

A **dependency edge** records that one work-item needs another completed first —
the standing, planned form of "do B after A". Before this, Orchestrarium had
only the TRANSIENT `BLOCKED:prerequisite` gate verdict on an in-flight agent run
and unstructured `$product-manager` "dependency notes" — so you could not see
"what is blocked by what" or "what is ready to start" without a run already
mid-flight. The `Depends-on:` edge makes that graph standing and derivable.

Dependencies are local task memory: `work-items/` is gitignored, so the edges
live on your machine; only the rules (in the role files and `CLAUDE.md` /
`AGENTS.md`) are committed.

## How an edge is declared

An optional `Depends-on:` line in the dependent item's `status.md`
`## Current state` block (the same place the `Epic:` join-key lives), but
**multi-valued** — a work-item may depend on several:

```
Depends-on: <slug>, <slug>
```

Targets are **work-items only**, resolved across THREE locations:
`work-items/active/`, `work-items/archive/` (the slug is stable across the
close-move), and the `## Backlog` *section* of `work-items/index.md` —
admitted-but-not-yet-started items (this is the index **section**, not a
`work-items/backlog/` directory; the index is the one documented backlog
authority). A backlog match is existence, not completion: an admitted item is
never `done`, so a dependency on it stays open until the target item is
actually finished. A slug that matches a bug, epic, or decision but no
work-item — or that resolves in none of the three locations — is a
**dangling** target by design — bugs/epics/decisions are not part of the
dependency graph.

## Derived views (never stored)

Nothing is cached; the views are computed live — on the Claude line by the
`/agents-status` + `/agents-resume` commands, and on the Codex line by the lead
scanning the active set (Codex has no commands):

- **blocked-by** of an item = its `Depends-on` targets that are NOT archived.
  A status line or `closure.md` does not satisfy a dependency while the target
  remains in an active location. An item with ≥1 open target is reported as
  `blocked`.
- **ready-set** = active items whose every `Depends-on` target is done (or which
  have none) — the items safe to start now.
- **dangling** = a `Depends-on` slug that resolves in none of the three
  locations (`active/`, `archive/`, or the `## Backlog` section of
  `index.md`). In the checker script's own words, "cannot verify this
  dependency is satisfied" and "this dependency doesn't parse as existing"
  are the same epistemic state, and neither is evidence of readiness — so
  `dangling` is folded INTO `blocked-by`, never excluded from it; the two are
  NOT mutually exclusive.

`/agents-status` shows the blocked count, the ready-set, and any dangling edge;
`/agents-resume` warns when the item you are resuming is `blocked`.

## Rules ($lead)

- Record `Depends-on` when admitting or planning an item that needs prior work.
  When the `$product-manager` roadmap package's dependency notes name a
  cross-work-item prerequisite, turn that prose into a standing edge here.
- Do NOT start an item's implementation while it has an open blocker (an open
  `Depends-on` target). When a dependency closes, the dependent may become
  ready; `/agents-status` surfaces the newly-ready set.
- **Authoring integrity (no live cycle detection in the MVP):** self-dependency
  is forbidden, and you must not author a dependency cycle (`a -> ... -> a`).
  This is an authoring rule owned by `$lead`, not a runtime check — the MVP
  derives blocked-by / ready-set and flags dangling edges, but does not run
  cycle detection.

## Relation to the existing gate

`Depends-on` is a declared edge between two planned work-items; the `BLOCKED:*`
gate verdicts are runtime stops. They are related but NOT the same mechanism, and
the difference that matters is the RESOLUTION:

- `BLOCKED:prerequisite` is the in-flight discovery of unplanned adjacent work (a
  broken module, a missing migration); it is resolved by filing that work in the
  bug registry — NOT by adding a `Depends-on` edge (bugs are not dependency
  targets).
- `BLOCKED:dependency` is an EXTERNAL blocker (missing tool, access, info)
  surfaced to the user.
- `Depends-on` is neither: a standing, planned work-item→work-item dependency
  declared up front, which lets `/agents-status` show blockers without an item
  being mid-run.

So do not read `Depends-on` as "the persisted form of `BLOCKED:prerequisite`" —
that verdict routes to the bug registry, this edge routes between work-items.

## Known limitation

Dependency hygiene is **governance-enforced only**. No hook enforces the
`Depends-on` edges, so a forgotten blocker (an item started while a prerequisite
is still open) or a dangling edge is not structurally caught — the
archival Stop control does not see them. `/agents-status` surfacing
blocked / ready / dangling is the only standing prompt — and it runs ONLY when
you invoke the command (on the Codex line, when the lead scans); nothing runs in
the background and nothing VALIDATES the graph (no cycle check, no
target-exists check beyond the dangling flag you have to look at), so a cycle, a
dangling target, or a forgotten blocker is caught only if and when you look.

## Physical lifecycle V1

`Depends-on` resolves bare work-item slugs through the physical lifecycle
owner: `work-items/backlog/`, `work-items/active/`, and
`work-items/archive/YYYY-MM/`. A target is complete only when it uniquely
resolves as an archived identity with its required terminal evidence; an index
entry, a guessed status word, or a missing record never grants readiness.

## Terms and Abbreviations

- **Depends-on**: the multi-valued `status.md` line declaring the work-items an
  item needs completed first.
- **blocked-by**: an item's `Depends-on` targets that are not yet done (derived).
- **ready-set**: active items whose every dependency is done (or have none).
- **dangling**: a `Depends-on` slug with no matching work-item.
- **BLOCKED:prerequisite**: the transient gate verdict when an agent discovers
  unplanned adjacent work mid-run, resolved by filing it in the bug registry —
  distinct from `Depends-on` (a planned work-item→work-item edge), not its
  "persisted form".
- **BLOCKED:dependency**: the separate gate verdict for an external blocker
  surfaced to the user — NOT modeled by `Depends-on`.

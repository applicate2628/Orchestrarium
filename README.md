Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This branch is the benchmark archive and benchmark-planning workspace.

It preserves:

- immutable archived benchmark snapshots
- the checkpoint and method documents needed to interpret those snapshots
- the evidence artifacts behind the archived ranking surfaces
- a separate mutable area to design the next benchmark phase without changing the archive

## Start here

| File | Role |
|---|---|
| `MANIFEST.md` | compact inventory of what the package currently preserves |
| `AGENTS.md` | branch structure and document-class rules |
| `Archive/2026-04-16-first-baseline/README.md` | current frozen archive snapshot |
| `Archive/2026-04-16-first-baseline/Results/full-results-2026-04-16.md` | current full archived result table |
| `Archive/2026-04-16-first-baseline/Results/short-results-x1-x5-2026-04-16.md` | narrowed `X1..X5` basis surface |
| `Work/next-upgraded-pack/README.md` | active mutable workspace for the next upgraded pack |
| `Work/next-upgraded-pack/Results-drafts/short-results-current-2026-04-17.md` | current live short result table |
| `Work/next-upgraded-pack/Tooling/HOW-TO-USE-TESTS.md` | human guide for running the current tests |

## Package layout

| Path | Purpose |
|---|---|
| `Archive/` | immutable archived benchmark snapshots |
| `Archive/2026-04-16-first-baseline/` | current admitted baseline package |
| `Work/` | mutable future benchmark-pack workspaces |
| `Work/next-upgraded-pack/` | current next-wave workspace |

## Current archival rule

| Rule | Meaning |
|---|---|
| archived snapshots are frozen | new packs should not silently change old archived state |
| new work happens in `Work/` | fixture design, rerun plans, and upgraded packs belong there first |
| archive only after admission | once a new pack is admitted, archive it as a new dated snapshot |
| tooling stays with the snapshot | wrapper or helper files used by a snapshot remain versioned with that snapshot |
| this package is additive | later archive structure changes should extend this package, not erase it |
| local salvage stays outside the package | recovery leftovers may exist locally in ignored storage, but they are not part of the committed archive |

## Current checkpoint note

| Topic | Current read |
|---|---|
| current frozen snapshot | `Archive/2026-04-16-first-baseline/` |
| active mutable workspace | `Work/next-upgraded-pack/` |
| current live short checkpoint | `Work/next-upgraded-pack/Results-drafts/short-results-current-2026-04-17.md` |
| active mutable model-version note | `X3` now maps to `opus 4.7max` for future mutable work |
| archive model-version note | frozen archive keeps historical `opus 4.6max` labels because that snapshot must not be rewritten |
| local salvage layer | intentionally excluded from the committed package |
| archived narrowed basis | `X1..X5` |
| frozen rows inside archived basis | `X4` and `X5` |
| defer reason in archived basis | extreme current latency or availability drag for fresh fairness-sensitive testing |

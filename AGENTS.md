Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

# Benchmarks Branch Structure

This branch is a dedicated benchmark archive and benchmark-planning workspace.

Its job is to keep two top-level zones separate:

- immutable archived snapshots under `Archive/`
- mutable future-work workspaces under `Work/`

## Directory map

| Path | Purpose |
|---|---|
| `README.md` | human-facing entry point |
| `AGENTS.md` | structure, document classes, and operating rules for this branch |
| `Archive/` | immutable archived benchmark snapshots |
| `Archive/<snapshot>/Results/` | frozen result tables for one admitted snapshot |
| `Archive/<snapshot>/Method/` | benchmark design, notation, governance, and policy docs for that snapshot |
| `Archive/<snapshot>/Checkpoints/` | synthesized baseline, status, and research context for that snapshot |
| `Archive/<snapshot>/Evidence/` | admitted evidence artifacts supporting that snapshot |
| `Archive/<snapshot>/Tooling/` | benchmark-side helpers and wrappers referenced by that snapshot |
| `Work/` | mutable future benchmark-pack workspaces |
| `Work/<pack>/Planning/` | forward work for one upcoming benchmark pack |
| `Work/<pack>/Fixtures/` | mutable fixture and verifier area for one upcoming benchmark pack |
| `Work/<pack>/Evidence/` | mutable run evidence for one upcoming benchmark pack |
| `Work/<pack>/Checkpoints/` | mutable interpretation and status layer for one upcoming benchmark pack |
| `Work/<pack>/Results-drafts/` | draft result surfaces before archival admission |

## Document classes

| Class | Rules |
|---|---|
| `Archive snapshot` | frozen package; preserve as admitted historical state |
| `Results` | frozen outputs inside one snapshot; add new snapshots instead of silently rewriting old results |
| `Method` | benchmark contract and interpretation layer for one snapshot |
| `Checkpoints` | dated state syntheses that explain one snapshot |
| `Evidence` | admitted evidence that supports one snapshot |
| `Work` | mutable area for the next pack; proposals and execution planning live here |
| `Tooling` | scripts and wrapper assets referenced by a snapshot; keep them versioned with that snapshot |
| `Local salvage` | ignored local-only leftovers for recovery; never a canonical input surface |

## Operating rules

| Rule | Meaning |
|---|---|
| separate archive from work | archive snapshots under `Archive/` must not be used as the mutable work area |
| separate result from plan | if a document proposes future tests, it belongs in `Work/`, not in archived `Results/` |
| separate checkpoint from result | if a document explains or synthesizes state, it belongs in archived `Checkpoints/`, not in `Results/` |
| preserve dated evidence | do not erase prior admitted run syntheses when later reruns happen |
| preserve historical model labels inside archive | provider-version changes belong in mutable `Work/` or a future snapshot, not as silent rewrites of old admitted packages |
| keep links honest | when files move, update archive-facing links so the package remains navigable |
| prefer additive history | add new dated snapshots instead of mutating old archive packages into a new meaning |
| keep root simple | the root should stay as a navigation surface, not become a dumping ground |
| keep salvage out of git package | leftovers kept for recovery must stay in ignored local storage and must not become archive or work sources of truth |

## Next-phase expectation

The next benchmark phase should be designed inside `Work/<pack>/Planning/` first, then executed in that mutable workspace, and only after admitted evidence exists should it be archived as a new dated package under `Archive/`.

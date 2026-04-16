Date: 2026-04-16
Owner: `$knowledge-archivist`
Status: `PASS`

# Benchmark Package Manifest

This file is the compact inventory of what the `benchmarks` branch currently preserves.

## Package status

| Area | Status | Meaning |
|---|---|---|
| `Archive/` | canonical | frozen admitted benchmark snapshots |
| `Work/` | mutable | workspace for the next upgraded benchmark pack |

## Current preserved package

| `#` | Path | Class | Meaning |
|---|---|---|---|
| `1` | `Archive/2026-04-16-first-baseline/Results/` | canonical results | frozen full and short result surfaces |
| `2` | `Archive/2026-04-16-first-baseline/Method/` | canonical method | experiment design, notation, governance, and policy docs |
| `3` | `Archive/2026-04-16-first-baseline/Checkpoints/` | canonical checkpoints | baseline syntheses, status, and research surfaces |
| `4` | `Archive/2026-04-16-first-baseline/Evidence/` | canonical evidence | admitted evidence supporting the archived baseline |
| `5` | `Archive/2026-04-16-first-baseline/Tooling/` | canonical tooling | wrappers and helper assets referenced by the archived baseline |
| `6` | `Work/next-upgraded-pack/Planning/` | mutable work | next-phase planning and suspicious-row backlog |
| `7` | `Work/next-upgraded-pack/Fixtures/` | mutable work | future fixture and verifier workspace |
| `8` | `Work/next-upgraded-pack/Evidence/` | mutable work | future run evidence for the upgraded pack |
| `9` | `Work/next-upgraded-pack/Checkpoints/` | mutable work | future interpretation and status layer |
| `10` | `Work/next-upgraded-pack/Results-drafts/` | mutable work | draft result tables before future admission |

## What counts as canonical now

| Canonical read | Path |
|---|---|
| frozen baseline package | `Archive/2026-04-16-first-baseline/` |
| current full results | `Archive/2026-04-16-first-baseline/Results/full-results-2026-04-16.md` |
| current short basis results | `Archive/2026-04-16-first-baseline/Results/short-results-x1-x5-2026-04-16.md` |
| active mutable next-pack workspace | `Work/next-upgraded-pack/` |

## Model-version note

| Surface | Rule |
|---|---|
| `Archive/2026-04-16-first-baseline/` | keep historical `opus 4.6max` labels unchanged |
| `Work/next-upgraded-pack/` | use current mutable model naming, where `X3` now maps to `opus 4.7max` |

## Explicit non-package surfaces

| Surface | Why not included as package evidence |
|---|---|
| `Orchestrarium/src.*` and `Orchestrarium/shared/references/*` | source and repo-reference material, not benchmark output artifacts |
| local salvage leftovers from prior cleanup | kept only in ignored local storage when needed; not part of the branch package |
| remaining ambiguous root `.scratch` runtime or release leftovers | not clearly benchmark-canonical |
| remaining ambiguous `Orchestrarium/.scratch` leftovers | not clearly benchmark-canonical |

## Reading rule

| Rule | Meaning |
|---|---|
| use `Archive/` for admitted history | this is the frozen source of truth for the current baseline |
| use `Work/` for next-pack design and execution | future benchmark work must not mutate the archive |
| keep salvage out of versioned package | cleanup leftovers may be kept locally, but they must not ship as committed archive content |

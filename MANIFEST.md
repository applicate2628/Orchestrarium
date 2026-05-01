Date: 2026-04-16
Owner: `$knowledge-archivist`
Status: `PASS`

# Benchmark Package Manifest

This file is the compact inventory of what the `benchmarks` branch currently preserves.

## Package status

| Area | Status | Meaning |
|---|---|---|
| `Archive/` | canonical | frozen admitted benchmark snapshots |
| `Scenarios-v3/` | active discovery | admitted Scenarios-v3 roots and registry metadata |
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
| `11` | `Scenarios-v3/V3L02-adr-long-horizon-source-conflict/` | active discovery | first admitted v3 root; `binary tie remains` for `X1` vs `X3` |
| `12` | `Work/scenarios-v3-base/` | mutable work | Scenarios-v3 planning, templates, evidence, and draft results |

## What counts as canonical now

| Canonical read | Path |
|---|---|
| frozen baseline package | `Archive/2026-04-16-first-baseline/` |
| current full results | `Archive/2026-04-16-first-baseline/Results/full-results-2026-04-16.md` |
| current short basis results | `Archive/2026-04-16-first-baseline/Results/short-results-x1-x5-2026-04-16.md` |
| active v3 discovery | `Scenarios-v3/` |
| active v3 result draft | `Work/scenarios-v3-base/Results-drafts/v3l02-results-2026-05-01.md` |
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
| use `Scenarios-v3/` for admitted v3 roots | this is the active discovery root, not an archive |
| use `Work/` for next-pack design and execution | future benchmark work must not mutate the archive |
| keep salvage out of versioned package | cleanup leftovers may be kept locally, but they must not ship as committed archive content |

## Terms and Abbreviations

- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
- `V3L02`: first admitted Scenarios-v3 root for `L02 advisory.design-adr`.

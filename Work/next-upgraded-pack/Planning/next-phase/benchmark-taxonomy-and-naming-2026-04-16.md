Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This file defines the naming system for the upgraded benchmark pack.

The goal is to end the mixed `M`, `G`, and `W` naming surface.

## New naming rule

| Surface | Prefix | Meaning |
|---|---|---|
| atomic benchmark test | `T` | one runnable benchmark test with its own verifier and evidence |
| practical role line | `L` | one synthesized ranking line backed by one or more tests |
| overlay | `O` | one non-primary synthesis surface such as fallback-only or browser-runtime notes |

## Legacy status

| Legacy family | New status |
|---|---|
| `M01..M10` | legacy atomic-test aliases only |
| `G01..G18` | legacy atomic-test aliases only |
| `W1..W5` | legacy synthesis aliases only; not primary future line names |

## Migration rule

| Rule | Meaning |
|---|---|
| no new `M` IDs | upgraded-pack work must not mint new `M*` tests |
| no new `G` IDs | upgraded-pack work must not mint new `G*` tests |
| no new `W` IDs | upgraded-pack work must not mint new `W*` rows |
| new atomic tests use `T` only | all new benchmark tests should enter the system as `Tnn` |
| lines use `L` only | practical comparison rows should use `Lnn` plus semantic role names |
| overlays use `O` only | fallback or modality slices should use `Onn` plus semantic names |

## Reserved migration ranges

| Range | Reserved for |
|---|---|
| `T01..T10` | migrated legacy `M01..M10` atomic tests |
| `T11..T28` | migrated legacy `G01..G18` atomic tests |
| `T29+` | new upgraded-pack tests |

## Practical line IDs

| Line ID | Semantic name |
|---|---|
| `L01` | `research.repo-understanding` |
| `L02` | `design.architecture-and-planning` |
| `L03` | `constraints.risk-reasoning` |
| `L04` | `review.code-and-quality` |
| `L05` | `review.ui-static` |
| `L06` | `worker.general-implementation` |
| `L07` | `worker.systems-implementation` |
| `L08` | `worker.toolchain-root-ownership` |
| `L09` | `worker.ui-implementation` |
| `L10` | `worker.long-horizon-autonomy` |

## Overlay IDs

| Overlay ID | Semantic name | Legacy source |
|---|---|---|
| `O01` | `overlay.provenance-top-path-advisory` | `W1` |
| `O02` | `overlay.provenance-top-path-risk` | `W2` |
| `O03` | `overlay.provenance-top-path-worker` | `W3` |
| `O04` | `overlay.fallback-mechanical` | `W4` |
| `O05` | `overlay.fallback-reasoning` | `W5` |
| `O06` | `overlay.browser-runtime` | browser/runtime notes such as legacy Playwright slices |

## Near-term naming for new candidate probes

| Old working label | Upgraded-pack label |
|---|---|
| `G19` | `T29` |
| `G20` | `T30` |
| `G21` | `T31` |
| `G22` | `T32` |
| `G23` | `T33` |

## Reading rule

| Rule | Meaning |
|---|---|
| archive may still mention legacy aliases | historical docs do not need forced rewrite |
| upgraded-pack planning should prefer new IDs | planning, fixtures, and future results should talk in `T`, `L`, and `O` |
| when legacy references are still needed | write `Tnn / legacy Gxx` or `Onn / legacy Wx` during migration |

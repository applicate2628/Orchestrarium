Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

# Benchmarks Branch Structure

This branch is a dedicated benchmark archive and benchmark-planning workspace.

Its job is to keep active discovery, archive, and work zones separate:

- admitted Scenarios-v3 roots under `Scenarios-v3/`
- immutable archived snapshots under `Archive/`
- mutable future-work workspaces under `Work/`

## Directory map

| Path | Purpose |
|---|---|
| `README.md` | human-facing entry point |
| `AGENTS.md` | structure, document classes, and operating rules for this branch |
| `Scenarios-v3/` | active discovery root for admitted Scenarios-v3 roots and registry metadata |
| `Scenarios-v3/_registry/` | machine-readable v3 line, trigger, and admission metadata; not a score root |
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
| keep scenario discovery clean | `Scenarios-v3/` may contain only admitted v3 roots plus `_registry/`; drafts and diagnostics stay in `Work/` until admitted |
| separate archive from work | archive snapshots under `Archive/` must not be used as the mutable work area |
| separate result from plan | if a document proposes future tests, it belongs in `Work/`, not in archived `Results/` |
| separate checkpoint from result | if a document explains or synthesizes state, it belongs in archived `Checkpoints/`, not in `Results/` |
| preserve dated evidence | do not erase prior admitted run syntheses when later reruns happen |
| preserve historical model labels inside archive | provider-version changes belong in mutable `Work/` or a future snapshot, not as silent rewrites of old admitted packages |
| keep links honest | when files move, update archive-facing links so the package remains navigable |
| prefer additive history | add new dated snapshots instead of mutating old archive packages into a new meaning |
| keep root simple | the root should stay as a navigation surface, not become a dumping ground |
| keep salvage out of git package | leftovers kept for recovery must stay in ignored local storage and must not become archive or work sources of truth |

## Result publication format

When publishing or restating benchmark results in this branch, prefer the compact operator style over prose-heavy summaries.

| Rule | Meaning |
|---|---|
| publish results as compact tables first | do not lead with prose rankings when the user asked for results |
| start with model legend when several rows appear | use `ID | Label` before the main ranking table when more than one model family is referenced |
| use numbered result tables | main result tables should use the shape ``# | Линия | 1 | 2 | 3 ...`` |
| keep the archived short-basis layout as the default template | unless a newer admitted short template explicitly replaces it, restate current and future scenario results in the same layout family as `Archive/2026-04-16-first-baseline/Results/short-results-x1-x5-2026-04-16.md`: legend first, then the ranked `Линия` table, then separate note or caveat tables, and only then any raw scenario matrix if the user asks for it |
| keep one row per surface or line | result rows should be named by the comparison surface, lane, or line, not by commentary text |
| keep test mapping separate | when needed, add a second compact table ``# | Линия | Тесты`` instead of stuffing test IDs into the ranking table |
| keep caveats separate | penalties, blocked rows, and runtime notes belong in their own compact note tables |
| distinguish ranked rows from supplemental rows | blocked or exploratory rows such as runtime-stalled Gemini lanes must not be mixed into the main ranking table |
| prefer canonical labels from the active surface | use exactly the labels and ordering from the admitted archive or current mutable result surface, not ad hoc rephrasings |
| preserve archive wording inside archive reads | when restating archived results, keep the archived labels and model versions unchanged |
| for current mutable reads, prefer the live short table | default current-state restatements should align to `Work/next-upgraded-pack/Results-drafts/short-results-current-2026-04-18.md` or its later successor |

## Current preferred publication shapes

| Situation | Preferred source |
|---|---|
| default short-results layout template | `Archive/2026-04-16-first-baseline/Results/short-results-x1-x5-2026-04-16.md` |
| archived basis result | `Archive/2026-04-16-first-baseline/Results/short-results-x1-x5-2026-04-16.md` |
| current mutable compact result | `Work/next-upgraded-pack/Results-drafts/short-results-current-2026-04-18.md` |
| current main admitted ranking surface | `Work/next-upgraded-pack/Results-drafts/v2-full-s01-s33-n01-n07-results-2026-04-18.md` |
| current legacy supporting runnable surface | `Work/next-upgraded-pack/Results-drafts/x1-x3-current-runnable-pack-results-2026-04-17.md` |

## Next-phase expectation

The next benchmark phase should be designed inside `Work/<pack>/Planning/` first, then executed in that mutable workspace, and only after admitted evidence exists should it be archived as a new dated package under `Archive/`.

## Terms and Abbreviations

- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
- `Scenarios-v3`: active benchmark discovery generation after the archived baseline.

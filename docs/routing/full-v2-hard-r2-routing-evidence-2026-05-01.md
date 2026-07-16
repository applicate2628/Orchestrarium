Date: 2026-05-01
Owner: `$knowledge-archivist`
Status: `PASS / ARCHITECTURE-REVIEWED` on the 2026-05-01 model families · current-family currency: `ASSUMPTION (UNVERIFIED — lane priorities carried over from the gpt-5.5/opus-4.7 release, pending re-benchmark)`

> **Model-currency invalidation (2026-07-11).** The models benchmarked below are retired: the
> Codex side migrated `gpt-5.5`/`gpt-5.3` to the `gpt-5.6-sol`/`gpt-5.6-luna` family, and the
> Claude side's current flagship alias is `fable` (as of 2026-07), not the `opus 4.7max`-era row.
> Per the standing rule in both external-dispatch contracts, a model-family migration invalidates
> the routing-evidence `PASS`: every lane priority derived from these tables is carried over as
> `ASSUMPTION (UNVERIFIED)` until the RF12 benchmark is re-run — or the lane orders are explicitly
> re-affirmed — on the current model families. The frozen tables below remain valid as the
> historical record of the 2026-05-01 release; they no longer certify current-family routing.

> **Model-currency invalidation (2026-07-15).** The `externalCodexProfile` alternate Codex tier was
> migrated from the volume model `gpt-5.6-luna` to the balanced model `gpt-5.6-terra` (luna dropped
> from the enum). Per the same standing rule in the external-dispatch contracts, this Codex
> model-family change keeps the routing-evidence `PASS` at `ASSUMPTION (UNVERIFIED)` on the current
> families until the RF12 benchmark is re-run or the lane orders are explicitly re-affirmed.

## Purpose

This note translates the admitted benchmark release
`../benchmarks/Release/2026-05-01-full-v2-hard-r2` into the Orchestrarium routing
surface used by `externalPriorityProfiles`.

The release separates two things:

- a frozen `40`-slot correctness table for the current `full-v2-hard-r2` leaderboard
- a `12 + 1` RF12 line-priority read for routing by task shape

The tables in this file are the publication-durable Orchestrarium routing evidence snapshot. The
benchmark paths below are local provenance inputs used to prepare this snapshot; the installed
Orchestrarium routing policy must not depend on those sibling-repository files being present at
runtime or in a consumer checkout.

Independent architecture review completed on 2026-05-01 with `PASS`: the review checked routing
coherence, owner-boundary handling, legacy migration behavior, source-of-truth consistency,
validation coverage, and publication/install readiness for the control-plane change.

Local provenance source map:

| What | Source |
|---|---|
| `/40` model totals | `../benchmarks/Release/2026-05-01-full-v2-hard-r2/Results/full-v2-hard-r2-results-2026-05-01.md:40` |
| all `40` test slots | `../benchmarks/Release/2026-05-01-full-v2-hard-r2/Results/full-v2-hard-r2-results-2026-05-01.md:714` |
| `12 + 1` line summary | `../benchmarks/Release/2026-05-01-full-v2-hard-r2/Results/full-v2-hard-r2-results-2026-05-01.md:141` |
| final line priority | `../benchmarks/Release/2026-05-01-full-v2-hard-r2/Results/full-v2-hard-r2-results-2026-05-01.md:159` |
| preset routing summary | `../benchmarks/Release/2026-05-01-full-v2-hard-r2/Results/preset-priority-matrix-2026-05-01.md:1` |
| RF12 scorecard | `../benchmarks/Release/2026-05-01-full-v2-hard-r2/Results/rf12-role-fit-scorecard-2026-05-01.md:1` |

This is not a universal model ranking. `X1 / gpt-5.5` is the correctness-first row on the frozen
`/40` surface. `X3 / opus 4.7max` remains primary for compact, low-noise, hard-output-budget, and
original-pixel-localization tasks. `X4 / Claude China opus max` is a final-only comparator.
`X2 / gpt-spark` is lower-bound calibration.

## Release Score

| Row | Provider/profile | Current score | Use |
|---|---|---:|---|
| `X1` | `gpt-5.5` | `33 / 40` | correctness-first production row |
| `X3` | `opus 4.7max` | `31 / 40` | compact/output-budget production row |
| `X4` | Claude China opus max | `29 / 40` | final-only comparator |
| `X2` | `gpt-spark` | `10 / 40 + 4 NR` | lower-bound calibration |

## 40-Slot Result Table

Legend: `P` means scoreable pass, `F` means scoreable fail, and `NR` means runtime, quota, route,
or no-summary not-run. Deprecated `X5` and `X6` rows are intentionally excluded from this operator
table because they are not part of current production routing.

| # | Line | Slot | X1 | X3 | X4 | X2 |
|---:|---|---|---|---|---|---|
| `01` | `L00` | `N17 owner orchestration` | `P` | `P` | `P` | `P` |
| `02` | `L00` | `N67 cross-phase integration owner` | `P` | `F` | `P` | `F` |
| `03` | `L00` | `N40 staged owner recovery` | `P` | `F` | `F` | `F` |
| `04` | `L00` | `N56 compact owner operator-budget` | `F` | `P` | `P` | `F` |
| `05` | `L01` | `S03 repo/advisory` | `P` | `P` | `P` | `P` |
| `06` | `L01` | `S04 knowledge/archive` | `P` | `P` | `P` | `F` |
| `07` | `L01` | `S06 source investigation` | `P` | `P` | `P` | `F` |
| `08` | `L02` | `S05 product/design ADR` | `P` | `P` | `P` | `P` |
| `09` | `L02` | `S07 architecture ADR` | `P` | `P` | `P` | `F` |
| `10` | `L02` | `S09 planning ADR` | `P` | `P` | `P` | `F` |
| `11` | `L03` | `S08 UI/UX structure` | `P` | `P` | `P` | `P` |
| `12` | `L03` | `N01 visual hierarchy` | `P` | `P` | `P` | `P` |
| `13` | `L03` | `N02 state flow trace` | `P` | `P` | `P` | `F` |
| `14` | `L04` | `N22 numerical stability` | `P` | `P` | `P` | `F` |
| `15` | `L04` | `N32 dual physics oracle` | `P` | `P` | `P` | `F` |
| `16` | `L04` | `N58 MoM batch runtime` | `F` | `P` | `P` | `F` |
| `17` | `L05` | `N35 staged interface migration` | `P` | `F` | `F` | `P` |
| `18` | `L05` | `N36 staged API migration` | `P` | `F` | `F` | `F` |
| `19` | `L05` | `N57 compact API migration` | `F` | `P` | `F` | `F` |
| `20` | `L06` | `N19 systems/toolchain` | `P` | `P` | `P` | `P` |
| `21` | `L06` | `N39 staged systems recovery` | `P` | `F` | `F` | `F` |
| `22` | `L06` | `N85 performance runtime budget` | `F` | `P` | `F` | `F` |
| `23` | `L07` | `N25 UI dirty-state repeat` | `P` | `P` | `F` | `F` |
| `24` | `L07` | `N47 UI operator-budget` | `F` | `P` | `P` | `F` |
| `25` | `L07` | `N60 UI visual-state reentry` | `P` | `P` | `P` | `F` |
| `26` | `L08` | `S22 adversarial geometry` | `P` | `P` | `P` | `F` |
| `27` | `L08` | `N110 visual micro-marker localization` | `F` | `P` | `F` | `NR` |
| `28` | `L08` | `N48 visual raster operator-budget` | `F` | `P` | `P` | `F` |
| `29` | `L09` | `S25 pre-pr review` | `P` | `P` | `P` | `F` |
| `30` | `L09` | `N03 generic review findings` | `P` | `P` | `P` | `F` |
| `31` | `L09` | `N04 regression triage` | `P` | `P` | `P` | `F` |
| `32` | `L10` | `S27 security review` | `P` | `P` | `P` | `F` |
| `33` | `L10` | `N05 secret exposure review` | `P` | `P` | `P` | `P` |
| `34` | `L10` | `N06 authz trust boundary` | `P` | `P` | `P` | `F` |
| `35` | `L11` | `S28 performance review` | `P` | `P` | `P` | `P` |
| `36` | `L11` | `N07 scalability/architecture review` | `P` | `P` | `P` | `F` |
| `37` | `L11` | `N37 staged adversarial review gate` | `P` | `F` | `F` | `P` |
| `38` | `L12` | `N80 calibrated screenshot grounding` | `P` | `F` | `P` | `NR` |
| `39` | `L12` | `N98 visual regression diff review` | `P` | `F` | `F` | `NR` |
| `40` | `L12` | `N105 staged screenshot-diff review` | `P` | `F` | `F` | `NR` |

## 12 + 1 Line Priority

`externalPriorityProfiles` can encode only the production provider order for external advisory,
worker, and review lanes. `L00 owner/control` is still part of the RF12 result, but owner roles such
as `$product-manager` and `$lead` have no generic external adapter and must fail fast if someone
tries to route them through an external worker or reviewer.

| Line | Config lane | `/40` read | Final priority |
|---|---|---|---|
| `L00 owner/control` | no external profile lane | `X1 3/4`, `X3 2/4`, `X4 3/4` | split: `X3` for compact owner packets; `X1` for staged owner, re-entry, integration-owner, QA-stop, and closeout |
| `L01 advisory.repo-understanding` | `advisory.repo-understanding` | all `3/3` | ordinary source ranking is `X1 / X3 near-tie`; compact source-conflict handoff uses `X3` |
| `L02 advisory.design-adr` | `advisory.design-adr` | all `3/3` | ordinary/source-ranked ADR remains near-tie and is deferred to Scenarios v3; staged ADR/review-gate closure uses `X1` |
| `L03 design.ui-ux-structure` | `design.ui-ux-structure` | all `3/3` | ordinary UX structure is near-tie; mixed visual/trace UX has `X3` diagnostic edge; staged UX re-entry uses `X1` |
| `L04 worker.reasoning-constraints` | `worker.reasoning-constraints` | `X1 2/3`, `X3 3/3`, `X4 3/3` | scientific correctness is near-tie; compact science/runtime with hard output budget uses `X3` |
| `L05 worker.default-implementation` | `worker.default-implementation` | `X1 2/3`, `X3 1/3`, `X4 0/3` | staged API/interface migration uses `X1`; compact single-shot implementation uses `X3` |
| `L06 systems/performance-worker` | `worker.systems-performance-implementation` | `X1 2/3`, `X3 2/3`, `X4 1/3` | staged systems recovery uses `X1`; compact performance hot-path work uses `X3` |
| `L07 worker.ui-implementation` | `worker.ui-implementation` | `X1 2/3`, `X3 3/3`, `X4 2/3` | compact UI state/render work uses `X3`; staged UI/visual-state accountability uses `X1` |
| `L08 worker.visual/graphics` | `worker.visual-graphics-visualization` | `X1 1/3`, `X3 3/3`, `X4 2/3` | compact raster/visual code and original-pixel localization use `X3`; staged visual delivery and screenshot review use `X1` |
| `L09 review.pre-pr` | `review.pre-pr` | all `3/3` | ordinary tuple-exact review is near-tie; staged source-bound review uses `X1`; compact low-noise runtime review uses `X3` |
| `L10 review.security` | `review.security` | all `3/3` | ordinary security review is near-tie; compact security root-cause review with hard output budget uses `X3` |
| `L11 review.performance-architecture` | `review.performance-architecture` | `X1 3/3`, `X3 2/3`, `X4 2/3` | staged source-bound performance/architecture review uses `X1`; single-shot review is near-tie unless budget is explicit |
| `L12 review.ui-visual-correctness` | `review.ui-visual-correctness` | `X1 3/3`, `X3 0/3`, `X4 1/3` | calibrated screenshot grounding, screenshot-diff review, and staged screenshot-diff review use `X1`; exact original-pixel extraction remains an `X3` worker/diagnostic subcase |

## Shipped Production Profiles

The shipped profiles keep Gemini and Qwen out of production `auto` routing. Advisory and review
lanes may use `reserve` only as the supplemental last candidate. Worker and design lanes must
not use `reserve`.

| Profile | Lane | Provider order |
|---|---|---|
| `balanced` | `advisory.repo-understanding` | `claude > codex > reserve` |
|  | `advisory.design-adr` | `claude > codex > reserve` |
|  | `design.ui-ux-structure` | `codex > claude` |
|  | `worker.reasoning-constraints` | `claude > codex` |
|  | `worker.default-implementation` | `codex > claude` |
|  | `worker.systems-performance-implementation` | `claude > codex` |
|  | `worker.ui-implementation` | `claude > codex` |
|  | `worker.visual-graphics-visualization` | `claude > codex` |
|  | `review.pre-pr` | `claude > codex > reserve` |
|  | `review.security` | `claude > codex > reserve` |
|  | `review.performance-architecture` | `codex > claude > reserve` |
|  | `review.ui-visual-correctness` | `codex > claude > reserve` |
| `quality-first` | `advisory.repo-understanding` | `codex > claude > reserve` |
|  | `advisory.design-adr` | `codex > claude > reserve` |
|  | `design.ui-ux-structure` | `codex > claude` |
|  | `worker.reasoning-constraints` | `claude > codex` |
|  | `worker.default-implementation` | `codex > claude` |
|  | `worker.systems-performance-implementation` | `codex > claude` |
|  | `worker.ui-implementation` | `claude > codex` |
|  | `worker.visual-graphics-visualization` | `claude > codex` |
|  | `review.pre-pr` | `codex > claude > reserve` |
|  | `review.security` | `codex > claude > reserve` |
|  | `review.performance-architecture` | `codex > claude > reserve` |
|  | `review.ui-visual-correctness` | `codex > claude > reserve` |

## Source Surfaces

| Source | Use |
|---|---|
| Embedded tables in this file | durable Orchestrarium routing snapshot for `/40` score, slot matrix, line summary, profile mapping, and priority matrix |
| `Release/2026-05-01-full-v2-hard-r2/Results/full-v2-hard-r2-results-2026-05-01.md` | local benchmark provenance for the `/40` score, slot matrix, line summary, and priority matrix |
| `Release/2026-05-01-full-v2-hard-r2/Results/rf12-role-fit-scorecard-2026-05-01.md` | local benchmark provenance for RF12 trigger-specific role-fit interpretation |
| `Release/2026-05-01-full-v2-hard-r2/Results/preset-priority-matrix-2026-05-01.md` | local benchmark provenance for compact preset routing summary |
| `Release/2026-05-01-full-v2-hard-r2/Evidence/full-v2-hard-r2-freeze-2026-04-30.json` | local benchmark provenance for machine-readable r2 replacement and final-fill evidence |

## Terms and Abbreviations

- `ADR`: Architecture Decision Record; a durable architecture decision note.
- `API`: Application Programming Interface; a public or internal programmatic contract.
- `authz`: authorization; permission and access-control behavior.
- `reserve`: symbolic supplemental read-only candidate for advisory/review lanes only; it is ranked after primary `claude` and `codex`.
- `CLI`: Command-Line Interface; a provider or tool launched from a shell.
- `externalPriorityProfile`: active named provider-order profile selected from `externalPriorityProfiles` when `externalProvider: auto` is used.
- `externalPriorityProfiles`: Orchestrarium `agents-mode` map from a named profile and lane to an ordered production provider list.
- `L00..L12`: RF12 line identifiers for the owner/control line plus twelve routing lines.
- `MoM`: Method of Moments; a numerical method used in computational electromagnetics.
- `NR`: not-run, used for runtime, quota, route, timeout, or missing-summary cells that are not scoreable model failures.
- `P` / `F`: scoreable pass or scoreable fail.
- `QA`: Quality Assurance; verification and regression-checking work.
- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
- `UI`: User Interface.
- `UX`: User Experience.
- `X1`, `X2`, `X3`, `X4`: benchmark row identifiers for provider/model routes.

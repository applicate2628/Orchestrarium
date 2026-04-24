Date: 2026-04-24
Owner: `$lead`
Status: `ACTIVE`

## Purpose

`full-v2-hard` is the current hardened replacement for the old full-v2 leaderboard.

The old `S01..S33 + N01..N07` `/40` table is retained only as a pre-v3 ceiling-effect baseline.
It is not used for current classification because it scored weak contracts and produced near-ceiling
rows such as `40 / 40` and `39 / 40`.

This surface keeps the same `40` score-slot shape:

- `12` routing lines times `3` slots = `36`
- `1` owner/control line times `4` slots = `4`
- total = `40`

## Current Hardened Score

| Row | Model/profile | Hardened `/40` | Scoreable detail | Current read |
|---|---|---:|---|---|
| `X1` | active `gpt-5.5` | `35 / 40` | `35 PASS`, `5 FAIL`, `0 NOT-RUN` | tied globally, but fails compact operator-budget slots |
| `X3` | `opus 4.7max` | `35 / 40` | `35 PASS`, `5 FAIL`, `0 NOT-RUN` | tied globally, but fails staged re-entry / ledger slots |
| `X5` | `gemini3.1pro` | `14 / 40` | `14 PASS`, `3 FAIL`, `23 NOT-RUN` | partial hardened calibration only; route/runtime unhealthy for recent waves |
| `X2` | `gpt-spark` | `5 / 40` | `5 PASS`, `14 FAIL`, `21 NOT-RUN` | partial hardened calibration only; lower-bound row |
| `X6` | `gemini3.1flash-lite-preview` | `1 / 40` | `1 PASS`, `6 FAIL`, `33 NOT-RUN` | partial hardened calibration only; many runtime-route/no-summary cells |
| `X4` | Claude China route | `0 / 40` | final-only; not admitted on this surface yet | hold for final closing comparison |

Interpretation: the current hardened `/40` is a global tie for `X1` and `X3`, but not a role tie.
The failure classes are different:

| Row | Scoreable fails inside the 40-slot surface | Failure class |
|---|---|---|
| `X1` | `N47`, `N48`, `N56`, `N57`, `N58` | preserved hidden semantics/physics/scope, but exceeded visible operator-output budget |
| `X3` | `N35`, `N36`, `N37`, `N39`, `N40` | missed staged re-entry, migration ledger, source binding, owner continuity, or closure semantics |

## Line Summary

| Line | Slots | `X1` | `X3` | Role read |
|---|---|---:|---:|---|
| `L00 owner/control` | `N17`, `N26`, `N40`, `N56` | `3 / 4` | `3 / 4` | split by execution shape: compact owner favors `X3`, staged owner favors `X1` |
| `L01 advisory.repo-understanding` | `S03`, `S04`, `S06` | `3 / 3` | `3 / 3` | near-tie |
| `L02 advisory.design-adr` | `S05`, `S07`, `S09` | `3 / 3` | `3 / 3` | near-tie for single-shot ADR |
| `L03 design.ui-ux-structure` | `S08`, `N01`, `N02` | `3 / 3` | `3 / 3` | near-tie |
| `L04 worker.reasoning-constraints` | `N22`, `N32`, `N58` | `2 / 3` | `3 / 3` | `X3` when compact low-noise output is a hard requirement; correctness remains near-tie |
| `L05 worker.default-implementation` | `N35`, `N36`, `N57` | `2 / 3` | `1 / 3` | `X1` for staged API/interface migration; `X3` for compact single-shot migration |
| `L06 worker.systems-performance-implementation` | `N19`, `N39`, `N59` | `3 / 3` | `2 / 3` | `X1` for staged systems recovery; `X3` keeps compact/perf rubric edge |
| `L07 worker.ui-implementation` | `N25`, `N47`, `N60` | `2 / 3` | `3 / 3` | `X3` for compact UI state/render work |
| `L08 worker.visual-graphics-visualization` | `S22`, `N21`, `N48` | `2 / 3` | `3 / 3` | `X3` for compact visual/raster work |
| `L09 review.pre-pr` | `S25`, `N03`, `N04` | `3 / 3` | `3 / 3` | near-tie on tuple-exact single-shot review |
| `L10 review.security` | `S27`, `N05`, `N06` | `3 / 3` | `3 / 3` | near-tie on tuple-exact security review |
| `L11 review.performance-architecture` | `S28`, `N07`, `N37` | `3 / 3` | `2 / 3` | `X1` for staged source-bound ADR/review gate |
| `L12 review.ui-visual-correctness` | `S29`, `S30`, `N43` | `3 / 3` | `3 / 3` | near-tie |

## Slot Matrix

Legend: `P` = scoreable pass, `F` = scoreable fail, `NR` = not-run/runtime-route/no-summary on this hardened slot.

| # | Line | Slot | X1 | X3 | X2 | X5 | X6 | Source |
|---:|---|---|---|---|---|---|---|---|
| `01` | `L00` | `N17 owner orchestration` | `P` | `P` | `P` | `NR` | `P` | `n17-owner-routing-rubric` |
| `02` | `L00` | `N26 owner recovery repeat` | `P` | `P` | `F` | `P` | `F` | `n26-owner-wave-rubric` |
| `03` | `L00` | `N40 staged owner recovery` | `P` | `F` | `F` | `NR` | `F` | `n40-staged-owner-rubric` |
| `04` | `L00` | `N56 compact owner operator-budget` | `F` | `P` | `F` | `NR` | `NR` | `n56-owner-operator-budget-rubric` |
| `05` | `L01` | `S03 repo/advisory` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `06` | `L01` | `S04 knowledge/archive` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `07` | `L01` | `S06 source investigation` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `08` | `L02` | `S05 product/design ADR` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `09` | `L02` | `S07 architecture ADR` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `10` | `L02` | `S09 planning ADR` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `11` | `L03` | `S08 UI/UX structure` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `12` | `L03` | `N01 visual hierarchy` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `13` | `L03` | `N02 state flow trace` | `P` | `P` | `F` | `P` | `F` | `v2-core12-tie-hardened`; E2 calibration |
| `14` | `L04` | `N22 numerical stability` | `P` | `P` | `F` | `NR` | `NR` | `n22-numerical-stability-rubric` |
| `15` | `L04` | `N32 dual physics oracle` | `P` | `P` | `F` | `NR` | `NR` | `n32-dual-physics-rubric` |
| `16` | `L04` | `N58 MoM batch runtime` | `F` | `P` | `F` | `NR` | `NR` | `n58-mom-batch-runtime-rubric` |
| `17` | `L05` | `N35 staged interface migration` | `P` | `F` | `P` | `NR` | `NR` | `n35-staged-interface-rubric` |
| `18` | `L05` | `N36 staged API migration` | `P` | `F` | `F` | `NR` | `NR` | `n36-staged-api-rubric` |
| `19` | `L05` | `N57 compact API migration` | `F` | `P` | `F` | `NR` | `NR` | `n57-compact-api-migration-rubric` |
| `20` | `L06` | `N19 systems/toolchain` | `P` | `P` | `P` | `NR` | `F` | `n19-systems-toolchain-rubric` |
| `21` | `L06` | `N39 staged systems recovery` | `P` | `F` | `F` | `NR` | `F` | `n39-staged-toolchain-rubric` |
| `22` | `L06` | `N59 real-repo performance cache` | `P` | `P` | `F` | `NR` | `NR` | `n59-perf-cache-rubric` |
| `23` | `L07` | `N25 UI dirty-state repeat` | `P` | `P` | `F` | `P` | `NR` | `n25-ui-dirty-repeat-rubric` |
| `24` | `L07` | `N47 UI operator-budget` | `F` | `P` | `NR` | `NR` | `NR` | `n47-ui-operator-budget-rubric` |
| `25` | `L07` | `N60 UI visual-state reentry` | `P` | `P` | `F` | `NR` | `NR` | `n60-ui-reentry-rubric` |
| `26` | `L08` | `S22 adversarial geometry` | `P` | `P` | `NR` | `NR` | `NR` | `x1-mainline-hardening-no-new-failures` |
| `27` | `L08` | `N21 visual raster` | `P` | `P` | `P` | `NR` | `NR` | `n21-visual-raster-rubric` |
| `28` | `L08` | `N48 visual raster operator-budget` | `F` | `P` | `NR` | `NR` | `NR` | `n48-visual-operator-budget-rubric` |
| `29` | `L09` | `S25 pre-pr review` | `P` | `P` | `NR` | `F` | `NR` | `v2-core12-tie-hardened` |
| `30` | `L09` | `N03 generic review findings` | `P` | `P` | `NR` | `F` | `NR` | `v2-core12-tie-hardened` |
| `31` | `L09` | `N04 regression triage` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `32` | `L10` | `S27 security review` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `33` | `L10` | `N05 secret exposure review` | `P` | `P` | `NR` | `F` | `NR` | `v2-core12-tie-hardened` |
| `34` | `L10` | `N06 authz trust boundary` | `P` | `P` | `NR` | `P` | `NR` | `v2-core12-tie-hardened` |
| `35` | `L11` | `S28 performance review` | `P` | `P` | `NR` | `NR` | `NR` | wave-2 tuple-exact hardening |
| `36` | `L11` | `N07 scalability/architecture review` | `P` | `P` | `NR` | `NR` | `NR` | wave-2 tuple-exact hardening |
| `37` | `L11` | `N37 staged adversarial review gate` | `P` | `F` | `P` | `NR` | `NR` | `n37-staged-review-rubric` |
| `38` | `L12` | `S29 accessibility/UI review` | `P` | `P` | `NR` | `NR` | `NR` | wave-2 tuple-exact hardening |
| `39` | `L12` | `S30 UX interaction review` | `P` | `P` | `F` | `NR` | `F` | E2 hardened separator slice |
| `40` | `L12` | `N43 UI immutable-test hotfix` | `P` | `P` | `NR` | `NR` | `NR` | `x1-mainline-hardening-no-new-failures` |

## Scoring Rules

| Rule | Contract |
|---|---|
| binary score | one slot contributes `1` only for scoreable verifier/scorer `PASS` |
| scoreable fail | wrapper/route completed and verifier/scorer rejected the artifact |
| runtime/quota | usage limit, timeout, no summary, route failure, missing worker output, and provider transport errors are `NR`, not model `FAIL` |
| active X1 | `X1` means active `gpt-5.5`; older `gpt-5.4` rows are used only where superseded by the `74 / 74` binary refresh or explicitly noted as historical rubric evidence |
| rubric | `0..100` rubrics are secondary lane-fit evidence; they do not replace the `/40` binary count |
| promotion | diagnostic rows become `full-v2-hard` score slots only after they have hardened verifier/scorer evidence and a clear role-line replacement reason |

## Current Routing Consequence

| Need | Current primary |
|---|---|
| staged delivery/re-entry, staged API/interface migration, staged systems recovery, staged owner recovery, staged review/ADR gate | `X1` |
| compact single-session implementation, compact UI/visual/raster, compact owner packet, compact real-repo API migration, compact low-noise science/runtime | `X3` |
| pure scientific correctness without strict output budget | `X1` / `X3` near-tie |
| tuple-exact single-shot review/security/source investigation | `X1` / `X3` near-tie |
| lower-bound calibration | `X2` first, `X6` second when route produces scoreable output |
| Gemini Pro | keep historical `X5` passes, but do not promote new claims until route/runtime health returns |

## Source

| Source | Role |
|---|---|
| `v2-core12-tie-hardened-results-2026-04-20.md` | admitted hardened core12 slots for `S03`, `S04`, `S05`, `S06`, `S07`, `S08`, `S09`, `S25`, `S27`, `N01`, `N02`, `N03`, `N04`, `N05`, `N06` |
| `role-fit-scorecard-v1-2026-04-22.md` | lane-fit interpretation and current hardening wave summaries |
| `short-results-current-2026-04-18.md` | compact operator-facing live status through `N60` |
| `../Evidence/x1-mainline-hardening-no-new-failures-2026-04-21.md` | admitted mainline hardening record |
| `../Evidence/n17-owner-routing-rubric-2026-04-22.json` through `../Evidence/n60-ui-reentry-rubric-2026-04-24.json` | machine-readable rubric/scorer evidence for promoted diagnostic slots |

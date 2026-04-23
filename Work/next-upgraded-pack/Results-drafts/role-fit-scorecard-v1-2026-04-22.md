Date: 2026-04-22
Owner: `$lead`
Status: `PASS`

## Purpose

This is the first role-fit scorecard for choosing which row should be preferred for each benchmark
lane. It is not a single global leaderboard. It separates:

- binary correctness winner
- diagnostic rubric winner
- compactness / cost winner
- test-coverage tendency
- near-tie lanes that still need more evidence before routing policy changes

## Evidence Basis

| Surface | Use in this scorecard |
|---|---|
| `v2-full-s01-s33-n01-n07-results-2026-04-18.md` | pre-v3 six-row baseline and lower-row calibration |
| `v2-core12-tie-hardened-results-2026-04-20.md` | hardened `X1` / `X3` / `X5` read for advisory, design, generic review, and security review |
| `v2-extra-lane-n08-n10-results-2026-04-20.md` | `E1 worker.long-autonomous` extra-lane read |
| `v2-top-pair-rubric-e3-results-2026-04-20.md` | narrow rubric read over `N11..N13`; `X1 60 / 60`, `X3 59 / 60` |
| `x1-mainline-hardening-no-new-failures-2026-04-21.md` | admitted hardening record for `N06`, wave 2, `S06`, `S22`, and `N14..N36` |
| `n16-long-horizon-rubric-2026-04-22.json` | `E6` long-horizon integration rubric; `X3 95 / 100`, `X1 89 / 100` |
| `n17-owner-routing-rubric-2026-04-22.json` | `E7` owner/orchestration routing rubric; `X1`, `X2`, `X3`, and `X6` all `100 / 100`; `X5` runtime `NOT-RUN` after failed smoke |
| `n18-scientist-constraints-rubric-2026-04-22.json` | `E8` scientist/constraints rubric; `X1`, `X2`, and `X3` all `100 / 100`; `X6` route-fails with partial `60 / 100`; `X5` semantic run times out |
| `n19-systems-toolchain-rubric-2026-04-22.json` | `E9` systems/toolchain rubric; `X3 95 / 100`, `X1 86 / 100`, `X2 84 / 100`, `X6 65 / 100 FAIL` |
| `n20-ui-interaction-rubric-2026-04-22.json` | `E10` UI interaction rubric; `X3 95 / 100`, `X1 87 / 100`, `X2 57 / 100 FAIL`, `X6 ROUTE-FAIL` |
| `n21-visual-raster-rubric-2026-04-22.json` | `E11` visual raster rubric; `X3 100 / 100`, `X1 89 / 100`, `X2 85 / 100`; `X5` and `X6` runtime no-summary after launch |
| `n22-numerical-stability-rubric-2026-04-22.json` | `E12` numerical stability rubric; `X1 100 / 100`, `X3 99 / 100`, `X2 10 / 100 FAIL`, `X6 ROUTE-FAIL` |
| `n23-owner-recovery-rubric-2026-04-22.json` | `E13` owner recovery rubric; `X3 100 / 100`, `X1 90 / 100`, `X2 70 / 100 FAIL`, `X6 ROUTE-FAIL` |
| `n24-toolchain-repeat-rubric-2026-04-22.json` | `E14` systems/toolchain repeat; `X3 95 / 100`, `X1 86 / 100`; `X2`, `X5`, and `X6` scoreable `FAIL` |
| `n25-ui-dirty-repeat-rubric-2026-04-22.json` | `E15` UI dirty-state repeat; `X5 98 / 100`, `X3 97 / 100`, `X1 86 / 100`; `X2 FAIL`, `X6 ROUTE-FAIL` |
| `n26-owner-wave-rubric-2026-04-22.json` | `E16` owner recovery repeat; `X3 100 / 100`, `X5 100 / 100`, `X1 92 / 100`; `X2` and `X6` scoreable `FAIL` |
| `n27-release-train-rubric-2026-04-22.json` | `E17` long-horizon integration repeat; `X3 92 / 100`, `X1 88 / 100`, `X2 88 / 100`; `X6 ROUTE-FAIL`, `X5 REQUEUE` after failed smoke |
| `n28-incident-repair-rubric-2026-04-22.json` | `E18` cross-role incident repair repeat; `X3 99 / 100`, `X1 93 / 100`; `X2` scoreable `FAIL 16 / 100`; `X6 ROUTE-FAIL`, `X5 REQUEUE` after smoke timeouts |
| `n29-ownership-budget-rubric-2026-04-23.json` | `E19` ownership-budget incident repair; `X3 100 / 100`, `X1 96 / 100`; both top-pair rows pass exact four-path budget; `X2` scoreable `FAIL 42 / 100`; `X6 RUNTIME-FAIL`, `X5 REQUEUE` |
| `n30-staged-delivery-rubric-2026-04-23.json` | `E20` staged delivery re-entry; `X1 PASS 96 / 100`, `X3 scoreable FAIL 91 / 100` after omitting one persisted phase ledger; `X2` scoreable `FAIL 66 / 100`; `X6 RUNTIME-FAIL`, `X5 REQUEUE` |
| `n31-mom-cylinder-rubric-2026-04-23.json` | `E21` computational electromagnetics MoM analytical oracle; `X3 PASS 94 / 100`, `X1 PASS 92 / 100`; both pass the PEC-cylinder MoM solver and cylindrical-harmonic oracle; calibration rows not launched |
| `n32-dual-physics-rubric-2026-04-23.json` | `E22` dual physics analytical oracle; `X3 PASS 100 / 100`, `X1 PASS 97 / 100`; both pass MoM plus hydrogenic radial Schrodinger oracle gates; `X2` scoreable `FAIL 33 / 100`; `X6` runtime no-summary; `X5` smoke REQUEUE |
| `n33-interface-refactor-rubric-2026-04-23.json` | `E23` interface refactor breakage; `X3 PASS 100 / 100`, `X1 PASS 96 / 100`; both pass hidden-consumer interface migration; `X2` scoreable `FAIL 5 / 100`; `X6` runtime no-summary |
| `n34-science-optimizer-rubric-2026-04-23.json` | `E24` high-load science optimizer; `X1 PASS 96 / 100`, `X3 PASS 96 / 100`; X1 faster on measured solver runtime, X3 much more compact; `X2` scoreable `FAIL 27 / 100` |
| `n35-staged-interface-rubric-2026-04-23.json` | `E25` staged interface migration re-entry; `X1 PASS 96 / 100`, `X3 scoreable FAIL 71 / 100`, `X2 PASS 91 / 100`; Gemini rows are runtime-route failures |
| `n36-staged-api-rubric-2026-04-23.json` | `E26` real-repo staged API migration; `X1 PASS 97 / 100`, `X3 scoreable FAIL 74 / 100`, `X2 scoreable FAIL 70 / 100`; X6 is runtime no-summary and X5 stayed smoke-gated |

## Decision Labels

| Label | Meaning |
|---|---|
| `primary` | preferred row for this lane under current evidence |
| `provisional-primary` | preferred row for now, but the edge is mainly efficiency/compactness or single-run evidence and needs repeat before hard policy |
| `secondary` | safe fallback or second opinion row |
| `near-tie` | no routing-grade separation; choose by availability, price, or desired style |
| `diagnostic-edge` | scored/rubric evidence favors a row, but binary gates still tie |
| `calibration-only` | useful for lower-bound context, not for top-pair lane assignment |
| `avoid-for-now` | current evidence or runtime behavior is too weak for this lane |

## Lane Fit Matrix

| Lane | Basis | X1 / gpt-5.4 | X3 / opus 4.7max | X2 / gpt-spark | X5 / gemini3.1pro | X6 / flash-lite | Current routing read |
|---|---|---|---|---|---|---|---|
| `advisory.repo-understanding` | `S03`, `S04`, `S06` | `near-tie`; hardened `3 / 3` | `near-tie`; hardened `3 / 3` | calibration weak: baseline `0 / 3` | viable: hardened `3 / 3` | weak: baseline `1 / 3` | keep `X1` and `X3` as co-primary; use `X5` only as secondary when runtime is healthy |
| `advisory.design-adr` | `S05`, `S07`, `S09` | `near-tie`; hardened `3 / 3` | `near-tie`; hardened `3 / 3` | calibration weak: baseline `0 / 3` | viable: hardened `3 / 3` | partial: baseline `2 / 3` | co-primary; prefer `X1` when trace/rubric discipline matters, `X3` when compactness matters |
| `design.ui-ux-structure` | `S08`, `N01`, `N02` | `near-tie`; hardened `3 / 3` | `near-tie`; hardened `3 / 3` | partial: baseline `1 / 3` | viable: hardened `3 / 3` | weak: baseline `1 / 3` | co-primary; no proven top-pair split |
| `worker.reasoning-constraints` | `S10`, `S11`, `S12`; plus `N18`, `N22`, `N31`, `N32`, and `N34` scored rubrics | `PASS` on `N18`, `N22`, `N31`, `N32`, and `N34`; fastest measured N34 solver runtime; verbose but exact | `PASS` on `N18`, `N22`, `N31`, `N32`, and `N34`; much more compact, but slower on N34 measured solver runtime | `PASS` on `N18`, scoreable `N22 FAIL`, scoreable `N32 FAIL 33`, scoreable `N34 FAIL 27`; calibration-only | `NOT-RUN` on N18 semantic timeout; not launched on N22/N31; `N32 REQUEUE`; not admitted on N34 | `ROUTE-FAIL` on N18 and N22; not launched on N31; `N32` runtime no-summary; N34 not launched after N33 timeout | co-primary for scientific/numerical correctness; use X1 when measured solver runtime dominates, X3 when output/cost compactness dominates |
| `worker.default-implementation` | `S15`, `S19`, `S20`; plus `N14`, `N15`, `N16`, `N27`, `N28`, `N29`, `N33`, `N35`, and `N36` diagnostics | passes current ordinary implementation pilots plus `N35` and `N36`; best for staged API/interface migration | compact winner on `N16`, `N27`, `N28`, `N29`, and `N33`, but scoreable `N35` and `N36` FAIL under staged re-entry | partial baseline `1 / 3`; passes `N27` and `N35`; fails `N36` and adjacent implementation repeats | baseline `3 / 3`; mostly route-gated on recent long tasks | baseline `3 / 3`; mostly route/runtime-gated on recent long tasks | split by execution shape: `X3 primary` for compact single-session implementation; `X1 primary` when staged re-entry/ledger accountability is part of the job |
| `worker.staged-delivery-reentry` | `N30`, `N35`, and `N36` staged runners with four fresh invocations over one run root | `PASS` on all three; `96 / 100` on N30/N35 and `97 / 100` on N36; kept persisted ledgers complete despite high output cost | scoreable `FAIL` on all three; N30 missed `03-review-response`; N35/N36 missed hidden runtime/API semantics and migration-ledger details | `N30 FAIL`; `N35 PASS 91 / 100`; `N36 FAIL 70 / 100` after bundle shape/scope issues | recent Gemini Pro staged rows are route/quota failures or smoke-gated | recent Flash staged rows are runtime-route/tool-loop/no-summary failures | `X1 primary` for multi-session delivery, staged API/interface migration, re-entry, and phase-ledger accountability |
| `worker.systems-performance-implementation` | `S13`, `S14`, `S21`; plus `N19` and `N24` systems/toolchain rubrics | `PASS` on `N19` and `N24`; both `86 / 100`; test-rich but high output cost | `PASS` on `N19` and `N24`; both `95 / 100`; compact and low output | `N19 PASS`; scoreable `N24 FAIL` after forbidden `.reports` bundle drift | `N24 FAIL` after smoke; missed cache-restore reason and summary source trace | scoreable `N19` and `N24 FAIL`; misses portable/cache/trace invariants | `X3 primary` for compact systems/toolchain patches; `X1 secondary` when explicit test augmentation matters |
| `worker.ui-implementation` | `S16`, `S17`, `S18`; plus `N20` and `N25` UI rubrics | `PASS` on `N20` and `N25`; `N25 86 / 100`; safe secondary | `PASS` on `N20` and `N25`; `N25 97 / 100`; compact and low output | scoreable `N20` and `N25 FAIL`; control-plane/shape issues | `N25 PASS 98 / 100` after smoke; strong UI contender but needs another modern UI-family pass before global primary | `ROUTE-FAIL` on `N20` and `N25` | `X3 primary` for UI state/render patches versus X1; `X5` is a route-healthy contender; avoid `X2/X6` as primary |
| `worker.visual-graphics-visualization` | `S22`, `S23`, `S24`; hardened `S22`; plus `N21` visual raster rubric | hardened `S22 23 / 23`; `N21 PASS`, rubric `89 / 100`; visual correctness ties | hardened `S22 23 / 23`; `N21 PASS`, rubric `100 / 100`; compactness/cost wins | `N21 PASS`, rubric `85 / 100`; tests unchanged | `N21 RUNTIME-FAIL` after successful smoke and semantic no-summary timeout | `N21 RUNTIME-FAIL` after semantic no-summary timeout | co-primary for visual correctness; `X3 provisional-primary` for compact visual raster patches; Gemini visual preference remains unproven |
| `review.pre-pr` | `S25`, `N03`, `N04` | hardened `3 / 3` | hardened `3 / 3` | weak: baseline `0 / 3` | hardened weaker: `1 PASS`, `2 FAIL` | weak: baseline `0 / 3` | co-primary; do not use `X5` as primary for hardened generic review |
| `review.security` | `S27`, `N05`, `N06` | hardened `3 / 3` | hardened `3 / 3` | partial: baseline `2 / 3` | hardened weaker: `2 PASS`, `1 FAIL` | weak: baseline `0 / 3` | co-primary; `X2` can be cheap calibration on simple security tuples, not primary |
| `review.performance-architecture` | `S26`, `S28`, `N07` | baseline `3 / 3`; wave-2 hardened `S28 PASS` | baseline `3 / 3`; wave-2 hardened `S28 PASS` | partial: baseline `1 / 3` | partial: baseline `2 / 3` | weak: baseline `0 / 3` | co-primary; needs hardened `S26/N07` before stronger split |
| `review.ui-visual-correctness` | `S29`, `S30`, `S31` | baseline `2 / 3`, but hardened `S29/S30 PASS` | baseline `3 / 3`, hardened `S29/S30 PASS` | weak: baseline `0 / 3` | partial: baseline `2 / 3`; hardened `S30` timed out in E2 attempt | weak: baseline `1 / 3` | treat X1/X3 as near-tie after hardened reruns; baseline X1 `S29` fail is pre-v3 only |

## Overlay And Diagnostic Fit

| Overlay | Evidence | Current fit |
|---|---|---|
| `E1 worker.long-autonomous` | `N08..N10`, hardened tiebreaker | `X1`, `X3`, and `X5` all `3 / 3`; keep `X1/X3` near-tie, use `X5` only when runtime is healthy |
| `E2 top-pair-separator` | `N02`, `S30`, `N11..N13` fresh slice | `X1` and `X3` both `5 / 5`; no binary split |
| `E3 top-pair-rubric` | `N11..N13` structural rubric | diagnostic edge to `X1` by `1` point; useful for trace-heavy memo/review, not routing-grade alone |
| `E6 long-horizon integration rubric` | `N16` scored run roots | diagnostic edge to `X3` by `6` points; useful for compact long-horizon integration routing |
| `E7 owner-orchestration` | `N17` scored run roots | no correctness split; useful runtime/style signal: `X3` and `X6` produce much smaller artifacts than `X1` and `X2` |
| `E8 scientist/constraints` | `N18` scored run roots | no correctness split between `X1` and `X3`; `X3` has the compactness edge; `X2` passes as calibration; Gemini rows are runtime-route caveats |
| `E9 systems/toolchain` | `N19` scored run roots | diagnostic edge to `X3` by `9` points; `X6` separates lower with scoreable verifier fail |
| `E10 UI interaction` | `N20` scored run roots | diagnostic edge to `X3` by `8` points; `X2` scoreably fails control-plane shape; `X6` route-fails with partial UI misses |
| `E11 visual raster provider-fit` | `N21` scored run roots | binary correctness ties `X1`/`X3`; diagnostic edge to `X3` by `11` points from output compactness; `X2` passes; `X5/X6` runtime no-summary after launch |
| `E12 numerical stability` | `N22` scored run roots | no binary split; narrow scored edge to `X1` by `1` runtime point; `X3` is far more compact; `X2` separates lower scoreably |
| `E13 owner recovery` | `N23` scored run roots | binary still ties, but scored owner recovery favors `X3` by `10` points; `X2` scoreably fails bundle shape; `X6` route-fails |
| `E14 systems/toolchain repeat` | `N24` scored run roots | binary still ties, but repeat confirms `X3 95 / 100` versus `X1 86 / 100`; `X2`, `X5`, and `X6` are scoreable lower-model verifier failures |
| `E15 UI dirty-state repeat` | `N25` scored run roots | binary correctness ties `X1`/`X3` but repeat confirms `X3` over `X1`; `X5` also passes and narrowly leads the N25 rubric; `X2` fails scoreably and `X6` route-fails |
| `E16 owner recovery repeat` | `N26` scored run roots | binary correctness ties `X1`/`X3` again, but repeat confirms `X3` over `X1`; `X5` also passes and ties `X3`, while `X2` and `X6` fail scoreably |
| `E17 long-horizon integration repeat` | `N27` scored run roots | binary correctness ties `X1`/`X3`; repeat confirms `X3` over `X1` on compactness/cost (`92` versus `88`); `X2` also passes as calibration, `X5` requeues on smoke quota, and `X6` route-fails |
| `E18 cross-role incident repair` | `N28` scored run roots plus X5 smoke attempts | binary correctness ties `X1`/`X3`; cross-role repair rubric favors `X3` (`99`) over `X1` (`93`); `X2` separates lower scoreably, `X5` requeues after smoke timeouts, and `X6` route-fails |
| `E19 ownership-budget incident repair` | `N29` scored run roots plus X5 smoke attempt | binary correctness ties `X1`/`X3` even with exact patch-budget gate; `X3` wins cost-only rubric (`100` versus `96`); `X2` separates lower scoreably, `X5` requeues after smoke timeout, and `X6` times out without summary |
| `E20 staged delivery re-entry` | `N30` staged runner roots plus X5 smoke attempt | first current hardened top-pair binary separator: `X1 PASS`, `X3 scoreable FAIL`; X3 passed scope/runtime/review but omitted one persisted phase ledger; `X2` scoreably fails via `.reports` drift; Gemini rows are runtime caveats |
| `E21 MoM analytical oracle` | `N31` scored run roots | binary correctness ties `X1`/`X3` on real computational electromagnetics; `X3` edges rubric (`94` versus `92`) by compactness while X1 is faster; no calibration rows launched |
| `E22 dual physics analytical oracle` | `N32` scored run roots plus X5 smoke attempt | binary correctness ties `X1`/`X3` on combined MoM PEC-cylinder and hydrogenic radial Schrodinger analytical-oracle task; measured solver-runtime scoring is present, but both top rows are fast enough for full runtime points; `X3 100`, `X1 97`; `X2` fails scoreably and Gemini rows are runtime caveats |
| `E23 interface refactor breakage` | `N33` scored run roots | binary correctness ties `X1`/`X3` on structured interface migration and hidden consumers; `X3 100`, `X1 96` by output compactness; `X2` separates lower scoreably |
| `E24 high-load science optimizer` | `N34` scored run roots | binary correctness ties `X1`/`X3`; both read `96`; X1 wins measured solver runtime, X3 wins output compactness; `X2` separates lower scoreably |
| `E25 staged interface migration re-entry` | `N35` staged runner roots | second current hardened top-pair binary separator: `X1 PASS`, `X3 scoreable FAIL`; validates that interface migration becomes X1-favored when combined with multi-session re-entry and phase-ledger accountability |
| `E26 real-repo staged API migration` | `N36` staged runner roots | third current hardened top-pair binary separator: `X1 PASS`, `X3 scoreable FAIL`; repeats the staged migration split on a BillingMesh-style API domain with hidden consumer contracts |

## Scorer Normalization Note

| Rule | Current use |
|---|---|
| within-lane comparison | raw rubric scores are usable for `X1` versus `X3` on the same scenario |
| cross-lane ranking | do not compare `N16`, `N19`, `N20`, `N21`, `N22`, `N23`, `N24`, `N25`, `N26`, `N27`, `N28`, `N29`, `N30`, `N31`, `N32`, `N33`, `N34`, `N35`, and `N36` as one global `0..100` leaderboard without splitting semantic and efficiency points |
| promotion threshold | promote a row to hard policy only after a semantic edge or an independent same-lane repeat; a one-run output/cost edge stays `provisional-primary` |
| diagnostic labels | current `X3` edges on implementation, owner recovery, and visual raster are useful routing preferences; systems/toolchain, UI, and owner recovery now have independent same-lane repeat evidence |

## Role-First Routing Read

| Roles | Lane | Primary | Secondary | Confidence | Why |
|---|---|---|---|---|---|
| `$product-manager`, `$lead` | owner, excluded from semantic routing lanes | `X3 primary` for compact owner recovery/routing packets versus X1 | `X1` for verbose trace-heavy recovery; `X5` is an owner-recovery contender after N26 but needs another owner-family pass before promotion | medium-high for X3 over X1; medium for X5 | N23 and N26 both keep binary PASS/PASS for X1/X3 but favor X3 by rubric; N26 also shows route-healthy X5 can pass and tie X3 |
| `$consultant`, `$knowledge-archivist`, `$analyst` | `advisory.repo-understanding` | `X1` / `X3 near-tie` | `X5` | medium | hardened advisory/repo evidence ties top pair and keeps X5 viable |
| `$product-analyst`, `$architect`, `$planner` | `advisory.design-adr` | `X1` when trace/rubric matters | `X3` when compactness matters | medium | E3 slightly favors X1 on source/denominator discipline, but binary gates tie |
| `$ux-designer` | `design.ui-ux-structure` | `X1` / `X3 near-tie` | `X5` | medium | hardened UI/UX structure ties top pair; no proven style-quality separator |
| `$algorithm-scientist`, `$computational-scientist`, `$security-engineer` | `worker.reasoning-constraints` | `X1` / `X3 near-tie`; choose X1 for runtime-sensitive solver work, X3 for compact exact output | `X2` calibration-only, not primary | medium | N18/N22/N31/N32/N34 keep X1/X3 scoreable; N34 adds high-load staged performance and reads X1 faster but X3 much more compact |
| `$backend-engineer`, `$data-engineer`, `$platform-engineer` | `worker.default-implementation` | `X3 primary` for compact single-session long-horizon, cross-role, ownership-budget, and ordinary interface-migration repairs | `X1` for verbose trace-heavy patch or staged accountability; `X2` calibration-only despite N27/N35 passes | high for compact single-session work; high for X1 on staged API/interface migration | N14/N15/N16/N27/N28/N29/N33 keep ordinary top-pair binary gates tied, while N35 and N36 prove staged migration is a separate X1-favored execution shape |
| `$backend-engineer`, `$platform-engineer`, `$lead` integration-owner simulations | `worker.staged-delivery-reentry` | `X1 primary` for staged re-entry and persisted phase-ledger accountability | `X3` for compact single-session slices only; use an explicit ledger checklist if X3 is selected for staged work | high from three binary separators | N30, N35, and N36 all use four fresh invocations and all produce `X1 PASS` versus `X3 scoreable FAIL`; N35/N36 tie the result to staged interface/API migration breakage |
| `$performance-engineer`, `$reliability-engineer`, `$toolchain-engineer` | `worker.systems-performance-implementation` | `X3 primary` for compact systems/toolchain patch | `X1` for test-rich patch; avoid `X2/X5/X6` as primary | medium-high | N19 and N24 both preserve binary correctness for X1/X3 and both give X3 a `9` point rubric edge; N24 separates X2/X5/X6 lower scoreably |
| `$frontend-engineer`, `$qt-ui-engineer`, `$model-view-engineer` | `worker.ui-implementation` | `X3 primary` for compact UI state/render patch versus X1 | `X1` as safe secondary; `X5` as route-healthy contender for form-state UI | medium-high for X3 over X1; medium for X5 | N20 and N25 both favor X3 over X1; N25 also shows X5 can pass and narrowly lead when Gemini Pro route is healthy |
| `$geometry-engineer`, `$graphics-engineer`, `$visualization-engineer` | `worker.visual-graphics-visualization` | `X3 provisional-primary` for compact raster patch; `X1` co-primary for correctness | `X2` calibration-only; Gemini rows not promoted | medium for geometry/raster correctness, low for Gemini preference | S22 and N21 tie X1/X3 by binary visual correctness; N21 cost edge favors X3, while X5/X6 timed out after launch |
| `$qa-engineer`, `$architecture-reviewer`, `$security-reviewer`, `$performance-reviewer`, `$accessibility-reviewer`, `$ux-reviewer`, `$ui-test-engineer` | review lanes | `X1` / `X3 near-tie` | `X5` only outside hardened generic/security review | medium | hardened tuple-exact review cells tie X1/X3 and separate X5 lower on pre-pr/security |
| `$external-worker`, `$external-reviewer` | adapters | not assigned here | not assigned here | none | adapter rows measure transport fidelity, not semantic skill; keep separate |

## Calibration Policy For X2 / X5 / X6

| Trigger | Run X2? | Run X5? | Run X6? | Reason |
|---|---|---|---|---|
| new X1/X3 result could change a routing lane | yes | yes, after Gemini smoke | yes | gives lower-bound and alternate-provider context |
| top pair ties by binary but rubric separates by more than `3` points | yes | optional | optional | checks whether rubric is only top-pair noise or a broader quality gradient |
| new task is long-horizon / integration / cross-role repair | yes | only if direct smoke writes worker output | only if runner has not recently no-output timed out | Gemini no-output hangs should stay runtime `NOT-RUN`, not model fail |
| review/security hardening | yes | yes | yes | prior evidence separates X5 lower here; useful to keep calibration fresh |
| cheap smoke / wrapper validation | yes | yes | yes | validates route health, not semantic quality |

## Current Operating Recommendation

| Need | Use |
|---|---|
| safest general top-pair answer when correctness matters and no style preference exists | `X1` and `X3` as near-tie; choose by availability |
| long-horizon / cross-role / ownership-budget repair, compact patch, low output cost | `X3 primary`, `X1 secondary`; `X2` remains calibration-only and fails N28/N29 scoreably |
| staged delivery, multi-session re-entry, phase-ledger accountability | `X1 primary`, `X3 secondary`; N30, N35, and N36 are binary separators on persisted phase-ledger / re-entry accountability |
| staged interface/API migration across fresh sessions | `X1 primary`, `X3 secondary`; N35 and N36 are `X1 PASS` versus `X3 scoreable FAIL` |
| patch where self-added tests/regression coverage are explicitly valued | `X1 primary`, `X3 secondary` |
| systems/toolchain ownership patch with path/cache/lock/fingerprint semantics | `X3 primary`, `X1 secondary`; avoid `X2/X5/X6` as primary |
| UI state/render/keyboard/form interaction patch | `X3 primary`, `X1 secondary`; consider `X5` when Gemini Pro route is healthy and another UI-family pass is not required |
| trace-heavy design memo, source-bound review, denominator/status reporting | `X1 slight primary`, `X3 secondary`; confidence is diagnostic-only |
| owner recovery under stale-source and interruption traps | `X3 primary`, `X1 secondary`; `X5` contender after N26; avoid `X2/X6` as primary |
| scientist/constraint decision memo or numerical physics solve with analytical oracle | `X1` / `X3 near-tie`; choose `X1` for trace-heavy evidence or when elapsed runtime matters, `X3` for compact exact output |
| runtime-sensitive scientific solver optimization | `X1 primary` only when measured runtime is the dominant constraint; `X3 secondary` for compactness |
| ordinary single-session interface refactor / migration patch | `X3 primary` for compact migration, `X1 secondary`; N33 ties by binary and favors X3 compactness |
| hardened review/security correctness | `X1` / `X3 near-tie`; avoid `X5` as primary until it clears hardened review rows |
| cheap lower-bound calibration | `X2` first, `X6` second; never promote from calibration without lane-specific evidence |
| visual raster/graphics patch | `X3 provisional-primary` for compact output, `X1` co-primary for correctness; Gemini preference remains unproven |

## Next Evidence Gaps

Use `Planning/next-phase/hardening-wave-roadmap-2026-04-22.md` as the live wave queue. The table
below is a compact routing view of the same queue.

| Gap | Best next pilot |
|---|---|
| owner/orchestration scored split needs confirmation only if becoming hard policy | complete for X3 versus X1: `N23` and `N26` both favor `X3`; `X5` needs another owner-family pass before promotion over X3 |
| long-horizon, cross-role, and ownership-budget integration evidence | complete for compact integration routing: `N16`, `N27`, `N28`, and `N29` all favor `X3` over `X1` while binary correctness ties |
| scientist/constraint lane still lacks a binary top-pair split | treat `N18`, `N22`, `N31`, `N32`, and `N34` as co-primary correctness evidence; N34 adds high-load performance and exposes X1 runtime edge versus X3 compactness edge |
| interface refactor hypothesis | N33 tied as a single-shot task, N35 split on staged interface migration, and N36 repeated the split on a real-repo-style staged API migration |
| next scientific computation hardening | no immediate synthetic follow-up; if policy needs runtime separation, use a stricter multi-session optimization task or real performance budget in a repo |
| systems/toolchain lane repeat evidence | complete: `N19` and `N24` both favor `X3 95 / 100` over `X1 86 / 100`; next repeat is not needed unless policy asks for another subdomain |
| UI implementation repeat evidence | complete for X3 versus X1: `N20` and `N25` both favor `X3`; `X5` needs one more UI-family pass before promotion over X3 |
| visual provider heuristic is not benchmark-proven | N21 proved top-pair raster correctness but both Gemini semantic rows timed out; repeat only after Gemini semantic route health is fixed |
| owner/orchestration compactness needs repeat evidence | complete for X3 versus X1 on recovery packets; repeat only if deciding between X3 and X5 or expanding owner work beyond recovery packets |

Date: 2026-04-24
Owner: `$lead`
Status: `PASS`

## Purpose

This is the first role-fit scorecard for choosing which row should be preferred for each benchmark
lane. It is not a single global leaderboard.

2026-04-24 update: active `X1` is now `gpt-5.5`. The fresh binary refresh passes `74 / 74`
unique scenarios on `S01..S33 + N01..N41`, and the hard-5 staged probe reads `X1 / gpt-5.5`
`5 / 5` versus admitted `X3 / opus 4.7max` `0 / 5` and `X4 / Claude China opus max` `1 / 5`.
Follow-up inverse probes `N42`, `N43`, and `N45` did not find an inverse `X1 FAIL / X3 PASS`
separator: both top rows pass when visible tests are protected and hidden consumers are added.
`N44` instead adds an `X1`-over-`X3` patch-hygiene separator on interface refactor/sourceId work:
X3 preserves hidden sourceId semantics but fails exact changed-path scope through `.pytest_cache`
drift. `N46` converts the compactness signal into a visible operator-budget gate and produces the
first honest compact single-session inverse separator: `X1 FAIL / X3 PASS`. `N47` repeats that
pattern on the UI dirty-state lane: both rows pass hidden UI semantics and exact scope, but X1 fails
the visible operator-budget gate while X3 stays compact. `N48` repeats the same split on visual
raster graphics with renderer-only scope and exact pixel semantics. `N49` tests the same explicit
operator-budget idea on the high-load scientific optimizer lane; both rows pass, so `binary tie
remains` there and X3's edge is only runtime rubric. `N50` repeats explicit operator budget on the
systems/toolchain immutable-CI line; both rows pass again, with X3's useful edge moving to elapsed
time rather than binary correctness. `N51` makes turnaround first-class and produces `both
scoreable FAIL`: X1 is correct but too verbose, X3 is compact/fast but incomplete. `N52` repeats
operator-budget pressure on interface refactor and also fails both: X1 is semantically correct but
far too verbose, X3 is compact but leaks `.pytest_cache`. `N53` isolates that ambiguity by ignoring
top-level generated `.pytest_cache/**`; both top rows then pass at `100 / 100`, so the interface
compactness probe returns to `binary tie remains`. `N54` then moves the same operator-budget gate to
the release-train long-horizon line and finds a fourth compact inverse separator: X1 preserves hidden
release-train semantics but fails output budget, while X3 passes all gates compactly. `N55` repeats
the same split on cross-role incident repair. `N56` repeats it on compact owner recovery: X1 passes
hidden owner-recovery semantics and scope but fails the visible output budget, while X3 passes all
gates compactly. The explicit
`X1 / gpt-5.4 xhigh` hard-5 comparison also passes `5 / 5`, so the staged X1-over-Claude split is
not solely a `gpt-5.5` refresh artifact.

It separates:

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
| `x1-mainline-hardening-no-new-failures-2026-04-21.md` | admitted hardening record for `N06`, wave 2, `S06`, `S22`, and `N14..N56` |
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
| `n37-staged-review-rubric-2026-04-23.json` | `E27` staged adversarial review gate; `X1 PASS 98 / 100`, `X3 scoreable FAIL 35 / 100`, `X2 PASS 97 / 100`; X3 missed ADR source binding, exact finding/non-claim ledgers, response cues, and closure; Gemini rows are route caveats |
| `n38-ui-visual-state-rubric-2026-04-23.json` | `E28` staged UI/visual/state integration; `X1 PASS 94 / 100`, `X2 scoreable FAIL 78 / 100`; `X3` is repeated runtime no-summary after three attempts and Gemini rows are route caveats |
| `n39-staged-toolchain-rubric-2026-04-23.json` | `E29` staged systems/toolchain re-entry; bounded-scope rerun reads `X1 PASS 94 / 100`, `X3 scoreable FAIL 78 / 100`, `X2 scoreable FAIL 76 / 100`, `X6 scoreable FAIL 78 / 100`; `X5` is route-fail |
| `n40-staged-owner-rubric-2026-04-23.json` | `E30` staged owner recovery re-entry; `X1 PASS 98 / 100`, `X3 scoreable FAIL 55 / 100`, `X2 scoreable FAIL 78 / 100`, `X6 scoreable FAIL 40 / 100`; `X5` is runtime-route |
| `n41-staged-incident-budget-rubric-2026-04-23.json` | `E31` staged incident-budget re-entry; `X1 PASS 100 / 100`, `X3 scoreable FAIL 78 / 100`, `X2 scoreable FAIL 78 / 100`; `X5` is runtime-route and `X6` is runtime no-summary |
| `x1-mainline-hardening-no-new-failures-2026-04-21.md` W22/W23 | `E32` systems immutable-CI and `E33` UI immutable-test inverse probes; `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass both probes with protected visible tests untouched |
| `n45-ownership-report-rubric-2026-04-24.json` | `E35` ownership-budget immutable report-consumer inverse probe; `X1 / gpt-5.5 PASS 96 / 100`, `X3 / opus 4.7max PASS 100 / 100`; binary tie remains and X3 wins only through output-cost points |
| `n46-operator-budget-rubric-2026-04-24.json` | `E36` operator-budget compact hotfix; `X1 / gpt-5.5 FAIL 70 / 100`, `X3 / opus 4.7max PASS 100 / 100`; X1 preserved hidden repair semantics but failed the visible output budget |
| `n47-ui-operator-budget-rubric-2026-04-24.json` | `E37` UI compact operator-budget hotfix; `X1 / gpt-5.5 FAIL 70 / 100`, `X3 / opus 4.7max PASS 94 / 100`; both pass hidden UI semantics and exact scope, but X1 fails the visible output budget |
| `n48-visual-operator-budget-rubric-2026-04-24.json` | `E38` visual raster compact operator-budget hotfix; `X1 / gpt-5.5 FAIL 70 / 100`, `X3 / opus 4.7max PASS 100 / 100`; both pass exact visual raster semantics and renderer-only scope, but X1 fails the visible output budget |
| `n49-science-operator-budget-rubric-2026-04-24.json` | `E39` scientific compact operator-budget optimizer; `X1 / gpt-5.5 PASS 96 / 100`, `X3 / opus 4.7max PASS 100 / 100`; both pass MoM plus hydrogenic Schrodinger semantics, exact scope, and visible output budget |
| `n50-systems-operator-budget-rubric-2026-04-24.json` | `E40` systems compact operator-budget hotfix; `X1 / gpt-5.5 PASS 99 / 100`, `X3 / opus 4.7max PASS 99 / 100`; both pass hidden stagegate semantics, protected CI hash, exact scope, and visible output budget |
| `n51-systems-turnaround-budget-rubric-2026-04-24.json` | `E41` systems turnaround-budget hotfix; both scoreable `FAIL`: X1 preserves hidden semantics but fails output budget, while X3 stays compact/fast but fails hidden stagegate semantics |
| `n52-interface-refactor-operator-budget-rubric-2026-04-24.json` | `E42` interface-refactor compact operator-budget; both scoreable `FAIL`: X1 preserves hidden interface semantics but fails output budget, while X3 stays compact but fails `.pytest_cache` scope/shape hygiene |
| `n53-interface-refactor-cache-ignored-rubric-2026-04-24.json` | `E43` interface-refactor cache-ignored operator-budget; both top rows pass `100 / 100` after top-level `.pytest_cache/**` is explicitly ignored as generated test cache |
| `n54-release-train-operator-budget-rubric-2026-04-24.json` | `E44` release-train compact operator-budget; `X1 FAIL 70 / 100`, `X3 PASS 92 / 100`; X1 preserves hidden release-train semantics and scope but fails visible output budget |
| `n55-incident-operator-budget-rubric-2026-04-24.json` | `E45` incident compact operator-budget; `X1 FAIL 70 / 100`, `X3 PASS 97 / 100`; X1 preserves hidden incident/reconciliation semantics and scope but fails visible output budget |

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
| `advisory.design-adr` | `S05`, `S07`, `S09`; plus staged `N37` ADR gate | single-shot near-tie; `N37 PASS 98 / 100` when ADR is part of staged source arbitration | single-shot near-tie; scoreable `N37 FAIL 35 / 100` after missing ADR source binding and downstream gate details | calibration weak in baseline but `N37 PASS 97 / 100` | viable in hardened baseline; `N37` Pro route stayed smoke-gated | partial baseline; `N37 ROUTE-FAIL` | split by execution shape: co-primary for ordinary single-shot ADR, `X1 primary` for staged ADR/review-gate closure |
| `design.ui-ux-structure` | `S08`, `N01`, `N02` | `near-tie`; hardened `3 / 3` | `near-tie`; hardened `3 / 3` | partial: baseline `1 / 3` | viable: hardened `3 / 3` | weak: baseline `1 / 3` | co-primary; no proven top-pair split |
| `worker.reasoning-constraints` | `S10`, `S11`, `S12`; plus `N18`, `N22`, `N31`, `N32`, `N34`, and `N49` scored rubrics | `PASS` on `N18`, `N22`, `N31`, `N32`, `N34`, and `N49`; fastest measured N34 solver runtime; adapts to explicit N49 compact-output budget | `PASS` on `N18`, `N22`, `N31`, `N32`, `N34`, and `N49`; much more compact on N34 and faster on N49 measured solver runtime | `PASS` on `N18`, scoreable `N22 FAIL`, scoreable `N32 FAIL 33`, scoreable `N34 FAIL 27`; calibration-only | `NOT-RUN` on N18 semantic timeout; not launched on N22/N31; `N32 REQUEUE`; not admitted on N34/N49 | `ROUTE-FAIL` on N18 and N22; not launched on N31; `N32` runtime no-summary; N34/N49 not launched after N33 timeout | co-primary for scientific/numerical correctness; N49 shows explicit compactness alone does not produce a binary split on the science optimizer lane |
| `worker.default-implementation` | `S15`, `S19`, `S20`; plus `N14`, `N15`, `N33`, `N44`, `N52`, and `N53` diagnostics | passes ordinary implementation pilots; more verbose but behavior-safe; `N44 PASS 96`; `N52 FAIL 70` only on output budget after hidden interface semantics pass; `N53 PASS 100` when generated cache is ignored | passes ordinary implementation pilots and leads by compactness on single-session refactor work; `N44 FAIL 72` and `N52 FAIL 70` from patch/cache hygiene, not hidden interface semantics; `N53 PASS 100` when generated cache is ignored | partial baseline `1 / 3`; `N33` scoreable fail | baseline `3 / 3`; recent long tasks mostly route-gated | baseline `3 / 3`; recent long tasks mostly runtime-gated | `X3 primary` for compact ordinary single-session implementation style, but do not treat interface compactness as a binary separator after N53; use `X1` when staged accountability, exact patch hygiene, trace, or test-led delivery dominates |
| `worker.owner-recovery` | `N23`, `N26`, and `N40` | `PASS` on all three; `N40 PASS 98 / 100` creates a staged owner separator | `PASS` on `N23` and `N26`, but `N40` scoreable `FAIL 55 / 100` | scoreable fails across the family | `N26 PASS 100 / 100`, but no scoreable staged-owner evidence on `N40` | `N23 ROUTE-FAIL`, `N26 FAIL`, `N40 FAIL 40 / 100` | split by execution shape: `X3 primary` for compact single-session owner recovery; `X1 primary` for staged owner recovery, re-entry, and runtime-policy closure |
| `worker.long-horizon-incident-repair` | `N16`, `N27`, `N28`, `N29`, `N45`, `N46`, `N54`, `N55`, and `N41` | passes semantic compact cells through `N45` and staged `N41`, but scoreably fails visible operator-budget on `N46` (`210369 > 40000`), `N54` (`300873 > 40000`), and `N55` (`352056 > 40000`) | passes compact single-session `N16/N27/N28/N29/N45/N46/N54/N55`, but `N41` scoreable `FAIL 78 / 100` | calibration-only; `N27 PASS`, but `N28/N29/N41` all fail scoreably | recent long-horizon family remains smoke-gated or route-fail; `N41` route-fails | route-fail or no-summary across the family; `N41` no final summary | split by execution shape: `X3 primary` for compact single-session long-horizon, release-train, cross-role, ownership-budget, and low-noise operator-budget repair; `X1 primary` for staged incident-budget re-entry with repair ledger, reentry state, exact patch budget, and closeout |
| `worker.staged-delivery-reentry` | `N30`, `N35`, and `N36` staged runners with four fresh invocations over one run root | `PASS` on all three; `96 / 100` on N30/N35 and `97 / 100` on N36; kept persisted ledgers complete despite high output cost | scoreable `FAIL` on all three; N30 missed `03-review-response`; N35/N36 missed hidden runtime/API semantics and migration-ledger details | `N30 FAIL`; `N35 PASS 91 / 100`; `N36 FAIL 70 / 100` after bundle shape/scope issues | recent Gemini Pro staged rows are route/quota failures or smoke-gated | recent Flash staged rows are runtime-route/tool-loop/no-summary failures | `X1 primary` for multi-session delivery, staged API/interface migration, re-entry, and phase-ledger accountability; N40/N41 show the same staged pattern extends beyond delivery |
| `worker.systems-performance-implementation` | `S13`, `S14`, `S21`; plus `N19`, `N24`, `N39`, `N42`, `N50`, and `N51` systems/toolchain probes | `PASS` on `N19`, `N24`, `N42`, `N50`, and staged `N39 94 / 100`; `N51 FAIL 70` from output budget after semantic pass | `PASS` on `N19`, `N24`, `N42`, and `N50`; `N51 FAIL 55` from hidden stagegate misses; staged `N39` scoreable `FAIL 78 / 100` after stale recovery source, wrong owner, quota classification, and ledger/closure misses | `N19 PASS`; scoreable `N24` and `N39 FAIL 76` | `N24 FAIL` after smoke and `N39` route-fail | scoreable `N19/N24/N39 FAIL` | split by execution shape: `X3 primary` for ordinary compact single-session systems/toolchain patches by rubric/elapsed time; `X1 primary` for staged systems/toolchain recovery; when the same compact hotfix has both hard output and turnaround budgets, N51 shows neither top row is cleanly dominant |
| `worker.ui-implementation` | `S16`, `S17`, `S18`; plus `N20`, `N25`, `N38`, `N43`, and `N47` UI probes | `PASS` on `N20`, `N25`, `N43`, and staged `N38 94 / 100`; `N47 FAIL 70` only on visible operator budget after hidden UI semantics pass | `PASS` on `N20`, `N25`, `N43`, and `N47`; `N38` stayed runtime no-summary | scoreable `N20`, `N25`, and `N38` FAIL | `N25 PASS 98 / 100`; `N38` route-fail | `ROUTE-FAIL` on `N20`; `N25` route-fail; `N38` route-fail | `X3 primary` for compact single-session UI state/render patches, especially when low-noise/operator-budget behavior is explicit; `N43` shows immutable visible tests alone do not make `X1` fail; staged UI/visual-state remains unresolved because `N38` produced only an `X1` scoreable pass and no scoreable `X3` result |
| `worker.visual-graphics-visualization` | `S22`, `S23`, `S24`; hardened `S22`; plus `N21`, `N38`, and `N48` visual-state evidence | hardened `S22 23 / 23`; `N21 PASS`, rubric `89 / 100`; `N38 PASS 94 / 100`; `N48 FAIL 70` only on visible operator budget after exact raster semantics pass | hardened `S22 23 / 23`; `N21 PASS`, rubric `100 / 100`; `N48 PASS 100`; `N38` no-summary | `N21 PASS`, rubric `85 / 100`; `N38` scoreable fail | `N21` and `N38` runtime-route / runtime-fail | `N21` and `N38` runtime-route / no-summary | `X3 primary` for compact single-session raster patches with low-noise/operator-budget requirements; co-primary for pure visual correctness; staged visual-state remains unresolved because `N38` never produced a scoreable `X3` result |
| `review.pre-pr` | `S25`, `N03`, `N04`; plus staged `N37` review gate | hardened single-shot `3 / 3`; `N37 PASS 98 / 100` on staged source-bound review closure | hardened single-shot `3 / 3`; scoreable `N37 FAIL 35 / 100` on staged ADR/findings/response gate | weak baseline but `N37 PASS 97 / 100` | hardened weaker and `N37` Pro smoke-gated | weak baseline; `N37 ROUTE-FAIL` | co-primary for ordinary tuple-exact review; `X1 primary` when review spans source arbitration, ADR, exact non-claims, response gate, and closure |
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
| `E27 staged adversarial review gate` | `N37` staged runner roots | fourth current hardened top-pair binary separator and first review/advisory staged separator: `X1 PASS`, `X3 scoreable FAIL`; promotes X1 for multi-session source arbitration, ADR traceability, exact finding/non-claim ledgers, response cues, and closure |
| `E28 staged UI/visual/state integration` | `N38` staged runner roots plus X3 reruns | useful positive X1 staged UI evidence (`PASS 94 / 100`), but not a top-pair separator because X3 never produced a scoreable final summary across three attempts; `X2` separates lower and Gemini rows are route caveats |
| `E29 staged systems/toolchain re-entry` | `N39` staged runner roots after bounded-scope redesign | seventh current hardened top-pair binary separator: `X1 PASS 94 / 100`, `X3 scoreable FAIL 78 / 100`; converts staged systems/toolchain recovery into an X1 lane while single-session systems/toolchain remains X3-favored |
| `E30 staged owner recovery re-entry` | `N40` staged runner roots | fifth current hardened top-pair binary separator: `X1 PASS 98 / 100`, `X3 scoreable FAIL 55 / 100`; converts owner recovery from an X3 single-session edge into an X1 staged re-entry lane |
| `E31 staged incident-budget re-entry` | `N41` staged runner roots | sixth current hardened top-pair binary separator: `X1 PASS 100 / 100`, `X3 scoreable FAIL 78 / 100`; converts staged long-horizon / ownership-budget incident repair into an X1 lane |
| `E32 systems immutable-CI` | `N42` cohort roots | negative inverse-separator evidence: `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass, both keep visible tests untouched, and both edit only production stagegate files |
| `E33 UI immutable-test` | `N43` cohort roots | negative inverse-separator evidence: `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass, both keep visible tests untouched, and both edit only production UI files |
| `E34 interface sourceId hidden consumer` | `n44-interface-sourceid-rubric-2026-04-24.json` | `X1 / gpt-5.5` passes at `96 / 100`; `X3 / opus 4.7max` scoreably fails at `72 / 100` due `.pytest_cache` changed-path drift, while hidden sourceId semantics still pass |
| `E35 ownership-budget report consumer` | `n45-ownership-report-rubric-2026-04-24.json` | negative inverse-separator evidence: both top rows pass hidden replay/report-consumer gates with exact three-path budget; X3 wins `100` versus X1 `96` solely from output cost |
| `E36 operator-budget compact hotfix` | `n46-operator-budget-rubric-2026-04-24.json` | first compact single-session inverse separator: X1 scoreably fails visible operator-budget while X3 passes all gates; this promotes X3 for low-noise compact hotfix lanes |
| `E37 UI compact operator-budget hotfix` | `n47-ui-operator-budget-rubric-2026-04-24.json` | second compact single-session inverse separator and first on UI: both top rows pass hidden UI semantics and exact scope, but X1 scoreably fails the visible operator-budget gate while X3 passes |
| `E38 visual raster compact operator-budget hotfix` | `n48-visual-operator-budget-rubric-2026-04-24.json` | third compact single-session inverse separator and first on visual graphics: both top rows pass exact raster semantics and renderer-only scope, but X1 scoreably fails the visible operator-budget gate while X3 passes |
| `E39 scientific operator-budget optimizer` | `n49-science-operator-budget-rubric-2026-04-24.json` | negative inverse-separator evidence: both top rows pass the full scientific optimizer, exact scope, and visible operator-budget gate; X3 wins rubric by measured runtime only |
| `E40 systems operator-budget compact hotfix` | `n50-systems-operator-budget-rubric-2026-04-24.json` | negative inverse-separator evidence: both top rows pass hidden systems semantics, protected CI hash, exact scope, and visible operator-budget gate; X3 wins only by elapsed time |
| `E41 systems turnaround-budget hotfix` | `n51-systems-turnaround-budget-rubric-2026-04-24.json` | tradeoff evidence, not a separator: both top rows fail scoreably; X1 is complete but too verbose, X3 is compact/fast but semantically incomplete |
| `E42 interface-refactor compact operator-budget` | `n52-interface-refactor-operator-budget-rubric-2026-04-24.json` | tradeoff evidence, not a separator: both top rows fail scoreably; X1 is semantically correct but extremely verbose, X3 is compact but leaks `.pytest_cache` |
| `E43 interface-refactor cache-ignored operator-budget` | `n53-interface-refactor-cache-ignored-rubric-2026-04-24.json` | negative inverse-separator evidence: both top rows pass hidden interface semantics, exact required-path scope after generated cache ignore, and visible operator budget; `binary tie remains` |
| `E44 release-train compact operator-budget` | `n54-release-train-operator-budget-rubric-2026-04-24.json` | fourth compact single-session inverse separator: X1 fails only the visible output budget after hidden release-train semantics pass; X3 passes all gates compactly |
| `E45 incident compact operator-budget` | `n55-incident-operator-budget-rubric-2026-04-24.json` | fifth compact single-session inverse separator: X1 fails only the visible output budget after hidden incident/reconciliation semantics pass; X3 passes all gates compactly |
| `E46 owner recovery compact operator-budget` | `n56-owner-operator-budget-rubric-2026-04-24.json` | sixth compact single-session inverse separator and first on compact owner recovery: X1 fails only the visible output budget after hidden owner-recovery semantics pass; X3 passes all gates compactly; X2 fails scoreably and X6 is runtime no-summary |
| `2026-04-24 X1 gpt-5.5 refresh` | `S01..S33 + N01..N41` fresh binary rerun | active `X1 / gpt-5.5` passes `74 / 74` unique scenarios; hard-5 staged subset is `5 / 5` and preserves the staged separator pattern against Claude-family rows |
| `2026-04-24 X1 gpt-5.4 hard-5 comparison` | `x1-gpt54-hard5-2026-04-24` staged roots | explicit `X1 / gpt-5.4 xhigh` comparison passes `N35`, `N36`, `N37`, `N39`, and `N41` with `wrapperExitCode=0` and verifier `PASS` |

## Scorer Normalization Note

| Rule | Current use |
|---|---|
| within-lane comparison | raw rubric scores are usable for `X1` versus `X3` on the same scenario |
| cross-lane ranking | do not compare `N16`, `N19`, `N20`, `N21`, `N22`, `N23`, `N24`, `N25`, `N26`, `N27`, `N28`, `N29`, `N30`, `N31`, `N32`, `N33`, `N34`, `N35`, `N36`, `N37`, `N38`, `N39`, `N40`, `N41`, `N42`, `N43`, `N44`, `N45`, `N46`, `N47`, `N48`, `N49`, `N50`, `N51`, `N52`, `N53`, `N54`, `N55`, and `N56` as one global `0..100` leaderboard without splitting semantic and efficiency points |
| promotion threshold | promote a row to hard policy only after a semantic edge or an independent same-lane repeat; a one-run output/cost edge stays `provisional-primary` |
| diagnostic labels | current `X3` edges on compact single-session implementation, systems/toolchain, UI, owner recovery, and visual raster remain useful routing preferences; `N39`, `N40`, and `N41` add semantic staged systems, staged owner, and staged incident separators in favor of `X1`, while `N38` remains unresolved |

## Role-First Routing Read

| Roles | Lane | Primary | Secondary | Confidence | Why |
|---|---|---|---|---|---|
| `$product-manager`, `$lead` | owner, excluded from semantic routing lanes | `X3 primary` for compact single-session owner recovery/routing packets, especially when low-noise operator budget is explicit; `X1 primary` when the owner packet is staged across recovery, route decision, runtime policy, and closeout | `X5` as a single-session owner contender only after another owner-family pass and route health; `X1` remains the safe verbose fallback | high for staged X1 vs compact X3; medium for X5 | N23 and N26 favor X3 on single-session owner recovery, N56 makes compact low-noise owner recovery binary `X1 FAIL / X3 PASS`, and N40 is a scoreable staged-owner separator: `X1 PASS 98`, `X3 FAIL 55` |
| `$consultant`, `$knowledge-archivist`, `$analyst` | `advisory.repo-understanding` | `X1` / `X3 near-tie` | `X5` | medium | hardened advisory/repo evidence ties top pair and keeps X5 viable |
| `$product-analyst`, `$architect`, `$planner` | `advisory.design-adr` | `X1` for staged source-bound ADR/review closure | `X3` for compact single-shot ADR when no staged gate is required | high for staged gates, medium for single-shot ADR | E3 only slightly favored X1, but N37 makes staged ADR/review closure a scoreable binary separator: X1 passed and X3 failed |
| `$ux-designer` | `design.ui-ux-structure` | `X1` / `X3 near-tie` | `X5` | medium | hardened UI/UX structure ties top pair; no proven style-quality separator |
| `$algorithm-scientist`, `$computational-scientist`, `$security-engineer` | `worker.reasoning-constraints` | `X1` / `X3 near-tie`; choose by measured runtime and desired artifact style rather than binary correctness | `X2` calibration-only, not primary | medium | N18/N22/N31/N32/N34/N49 keep X1/X3 scoreable; N49 shows explicit compactness can be satisfied by both top rows on the high-load science optimizer |
| `$backend-engineer`, `$data-engineer`, `$platform-engineer` | `worker.default-implementation` | `X3 primary` for compact ordinary single-session implementation style when cache/scope hygiene is controlled; `X1` when staged accountability, exact patch hygiene, or test-led source trace matters | `X2` calibration-only | medium | N14, N15, and N33 keep ordinary binary gates tied while compactness favors X3; N44 and N52 show exact changed-path/cache hygiene can flip or block the single-session refactor read, and N53 shows interface compactness itself is not a binary separator when generated cache is ignored |
| `$backend-engineer`, `$platform-engineer`, `$lead` integration-owner simulations | `worker.staged-delivery-reentry` | `X1 primary` for staged re-entry and persisted phase-ledger accountability | `X3` for compact single-session slices only; use an explicit ledger checklist if X3 is selected for staged work | high from three binary separators plus staged follow-on confirmation | N30, N35, and N36 all use four fresh invocations and all produce `X1 PASS` versus `X3 scoreable FAIL`; N40/N41 show the same staged accountability pattern outside delivery |
| `$backend-engineer`, `$platform-engineer`, `$lead` incident-owner simulations | `worker.long-horizon-incident-repair` | `X3 primary` for compact single-session incident, release-train, cross-role, ownership-budget, and low-noise operator-budget repair; `X1 primary` once the same family becomes staged re-entry | `X1` for staged repair-ledger/accountability work; `X2` calibration-only | high | N16/N27/N28/N29/N45 tie by binary and favor X3 on compactness/cost; N46, N54, and N55 make low-noise compact repair/release-train/incident work scoreable as `X1 FAIL`, `X3 PASS`; N41 is the staged separator: `X1 PASS 100`, `X3 FAIL 78` |
| `$performance-engineer`, `$reliability-engineer`, `$toolchain-engineer` | `worker.systems-performance-implementation` | `X3 primary` for ordinary compact single-session systems/toolchain patch; `X1 primary` for staged recovery / source arbitration / runtime-status closeout; use neither row without extra scrutiny when output budget and hard turnaround are both mandatory | avoid `X2/X5/X6` as primary | high for staged X1, medium for single-session X3 | N19 and N24 both preserve binary correctness for X1/X3 and give X3 a `9` point single-session rubric edge; N50 ties by binary under explicit output budget but X3 is faster; N51 shows hard compact+turnaround can fail both rows for different reasons; bounded N39 splits staged systems/toolchain as `X1 PASS 94` versus `X3 FAIL 78` |
| `$frontend-engineer`, `$qt-ui-engineer`, `$model-view-engineer` | `worker.ui-implementation` | `X3 primary` for compact single-session UI state/render patch, especially when output/noise budget is explicit; staged UI remains unresolved rather than overturned | `X1` as safe secondary and the only current scoreable staged UI pass; `X5` as route-healthy contender for single-session form-state UI | high for compact low-noise UI, medium for staged UI | N20 and N25 both favor X3 over X1 by rubric; N47 makes low-noise compact UI scoreable as `X1 FAIL`, `X3 PASS`; N38 gives X1 the only scoreable staged UI pass, but X3 never completed the staged packet |
| `$geometry-engineer`, `$graphics-engineer`, `$visualization-engineer` | `worker.visual-graphics-visualization` | `X3 primary` for compact single-session raster patch when output/noise budget is explicit; `X1` co-primary for pure correctness and staged visual-state delivery | `X2` calibration-only; Gemini rows not promoted | high for compact low-noise raster, medium for pure correctness, low for staged top-pair certainty | S22 and N21 tie X1/X3 by binary visual correctness; N48 makes low-noise raster repair scoreable as `X1 FAIL`, `X3 PASS`; N38 adds an X1 staged visual-state pass but no scoreable X3 completion |
| `$qa-engineer`, `$architecture-reviewer`, `$security-reviewer`, `$performance-reviewer`, `$accessibility-reviewer`, `$ux-reviewer`, `$ui-test-engineer` | review lanes | `X1` for staged source arbitration, ADR, response-gate closure; `X1` / `X3 near-tie` for ordinary tuple-exact single-shot review | `X3` for compact single-shot review; `X5` only outside hardened generic/security review | high for staged review gates, medium for ordinary review | tuple-exact review cells tie X1/X3, but N37 splits staged adversarial review gates sharply: X1 PASS 98, X3 scoreable FAIL 35 |
| `$external-worker`, `$external-reviewer` | adapters | not assigned here | not assigned here | none | adapter rows measure transport fidelity, not semantic skill; keep separate |

## Calibration Policy For X2 / X5 / X6

| Trigger | Run X2? | Run X5? | Run X6? | Reason |
|---|---|---|---|---|
| completed X1/X3 task could change a routing lane | yes | no while quota-deferred | yes | X2/X6 give paired lower-bound and alternate-provider context |
| top pair ties by binary but rubric separates by more than `3` points | yes | no while quota-deferred | optional | checks whether rubric is only top-pair noise or a broader quality gradient |
| new task is long-horizon / integration / cross-role repair | yes | no while quota-deferred | only if runner has not recently no-output timed out | Gemini no-output hangs stay runtime `NOT-RUN`, not model fail |
| review/security hardening | yes | no while quota-deferred | yes | prior evidence separates X5 lower here, but route quota blocks fresh use |
| final closing comparison | yes | yes if quota/route health returns | yes | validates the full final comparison set, with X4 reserved for that same closeout |

## Current Operating Recommendation

| Need | Use |
|---|---|
| safest general top-pair answer when correctness matters and no style preference exists | `X1 / gpt-5.5` and `X3` as near-tie on older single-shot correctness lanes; choose by execution shape and availability |
| long-horizon / cross-role / ownership-budget repair, compact patch, low output cost | `X3 primary` for single-session work, `X1 secondary`; `N45` confirms hidden report-consumer hardening still ties by binary while X3 wins cost, and `N46`, `N54`, plus `N55` turn explicit operator-budget into `X1 FAIL / X3 PASS` on repair, release-train, and incident lines; `X2` remains calibration-only and fails N28/N29/N41 scoreably |
| staged delivery, multi-session re-entry, phase-ledger accountability | `X1 / gpt-5.5 primary`, `X3 secondary`; N30, N35, and N36 are binary separators, and N40/N41 confirm that the staged-accountability split generalizes beyond delivery |
| staged interface/API migration across fresh sessions | `X1 primary`, `X3 secondary`; N35 and N36 are `X1 PASS` versus `X3 scoreable FAIL` |
| staged source-bound review, ADR, response-gate closure | `X1 primary`, `X3 secondary`; N37 is `X1 PASS 98 / 100` versus `X3 scoreable FAIL 35 / 100` |
| staged owner recovery / runtime-policy closure | `X1 primary`, `X3 secondary`; N40 is `X1 PASS 98 / 100` versus `X3 scoreable FAIL 55 / 100` |
| staged incident-budget / repair-ledger re-entry | `X1 primary`, `X3 secondary`; N41 is `X1 PASS 100 / 100` versus `X3 scoreable FAIL 78 / 100` |
| patch where self-added tests/regression coverage are explicitly valued | `X1 primary`, `X3 secondary` |
| systems/toolchain ownership patch with path/cache/lock/fingerprint semantics | `X3 primary` for ordinary compact single-session patches; `X1 primary` when the same lane is staged across recovery source arbitration, runtime-status discipline, ledger, and closeout; if hard output and turnaround budgets are both mandatory, N51 says verify both because the top pair can fail in opposite ways; avoid `X2/X5/X6` as primary |
| UI state/render/keyboard/form interaction patch | `X3 primary` for compact single-session work, `X1 secondary`; N47 makes explicit low-noise UI hotfixes `X3 primary` by binary gate; consider `X5` when Gemini Pro route is healthy; N38 leaves staged UI unresolved because X3 never completed scoreably |
| trace-heavy design memo, source-bound review, denominator/status reporting | `X1 slight primary`, `X3 secondary`; confidence is diagnostic-only |
| owner recovery under stale-source and interruption traps | `X3 primary` for compact single-session packets, now including explicit low-noise/operator-budget packets after N56; `X1 primary` once the packet is staged/re-entry based; `X5` remains quota-deferred contender after N26; avoid `X2/X6` as primary |
| scientist/constraint decision memo or numerical physics solve with analytical oracle | `X1` / `X3 near-tie`; choose `X1` for trace-heavy evidence, `X3` for compact exact output, and verify runtime on the actual task |
| runtime-sensitive scientific solver optimization | `X1` / `X3 near-tie`; N34 favored X1 runtime, N49 favored X3 runtime, so use fresh measured runtime instead of a fixed model preference |
| ordinary single-session interface refactor / migration patch | `X3 primary` for compact migration style when patch hygiene is controlled; `X1 primary` when exact changed-path budget, staged ledger accountability, and test/source trace are first-class; N33 and N53 tie by binary while favoring compact style, N44 flips to X1 on patch hygiene |
| hardened review/security correctness | `X1` / `X3 near-tie`; avoid `X5` as primary until it clears hardened review rows |
| cheap lower-bound calibration | `X2` first, `X6` second; never promote from calibration without lane-specific evidence |
| visual raster/graphics patch | `X3 primary` for compact single-session low-noise raster work after N48; `X1` co-primary for pure correctness and staged visual-state delivery; Gemini preference remains unproven |

## Next Evidence Gaps

Use `Planning/next-phase/hardening-wave-roadmap-2026-04-22.md` as the live wave queue. The table
below is a compact routing view of the same queue.

| Gap | Best next pilot |
|---|---|
| owner/orchestration scored split needs confirmation only if becoming hard policy | single-session owner recovery is complete for X3 versus X1 (`N23`, `N26`); staged owner recovery is now also complete for X1 versus X3 (`N40`); `X5` still needs another owner-family pass before promotion over X3 on the single-session branch |
| long-horizon, cross-role, and ownership-budget integration evidence | complete on both branches: `N16`, `N27`, `N28`, `N29`, and `N45` favor `X3` for compact single-session work by rubric/cost while tying by binary; `N46`, `N54`, and `N55` are low-noise/operator-budget compact separators in favor of `X3`; `N41` is a staged separator in favor of `X1` |
| scientist/constraint lane still lacks a binary top-pair split | treat `N18`, `N22`, `N31`, `N32`, `N34`, and `N49` as co-primary correctness evidence; N49 confirms explicit compactness does not by itself create a science-lane binary split |
| interface refactor hypothesis | N33 tied as a single-shot semantic task, N44 adds an X1-over-X3 patch-hygiene split without hidden sourceId semantic failure, N35 split on staged interface migration, and N36 repeated the staged split on a real-repo-style API migration |
| staged review/advisory gate policy | complete for X1 versus X3: N37 splits top pair scoreably and supports X1 primary for staged source arbitration, ADR traceability, response-gate closure, and exact non-claim ledgers |
| next scientific computation hardening | no immediate synthetic follow-up; if policy needs runtime separation, use a stricter multi-session optimization task or real performance budget in a repo |
| systems/toolchain lane repeat evidence | complete on both branches: `N19` and `N24` favor `X3 95 / 100` over `X1 86 / 100` for compact single-session work; `N42` and `N50` show immutable-CI plus explicit output budget still tie top pair by binary; `N51` makes hard turnaround first-class and yields both-fail tradeoff evidence; bounded `N39` favors `X1 PASS 94` over `X3 FAIL 78` for staged systems/toolchain recovery |
| inverse `X1 FAIL / X3 PASS` search | `N46` found the first honest compact single-session inverse separator by making low-noise/operator-budget behavior a visible hard gate; `N47` repeats it on UI, `N48` repeats it on visual raster, `N54` repeats it on release-train long-horizon integration, `N55` repeats it on cross-role incident repair, and `N56` repeats it on compact owner recovery. `N49`, `N50`, and `N53` do not repeat it on scientific optimizer, systems/toolchain, or cache-ignored interface refactor because both top rows pass the explicit budget. `N51` does not produce inverse separation because both fail under combined compact+turnaround+semantics constraints. `N52` does not produce inverse separation because X3 stays compact but leaks `.pytest_cache`; N53 closes that ambiguity as PASS/PASS after cache ignore. Earlier attempts `N42`, `N43`, and `N45` tied; `N44` went the other way through X3 patch-hygiene drift |
| next inverse probe | Cache-ignored interface compactness is now closed as `binary tie remains`, and compact owner recovery now has N56; continue only in other lanes where pass/pass still hides a real role distinction, especially real-repo compact workflows or unresolved staged UI/visual-state |
| UI implementation repeat evidence | single-session evidence is complete for X3 versus X1: `N20` and `N25` both favor `X3`, and `N47` adds a binary `X1 FAIL / X3 PASS` low-noise UI hotfix separator; staged UI remains unresolved because `N38` produced only an `X1` scoreable pass while `X3` timed out without summary; `X5` still needs one more UI-family pass before promotion over X3 |
| visual provider heuristic is not benchmark-proven | N21 proved top-pair raster correctness and N48 adds an X3-over-X1 low-noise raster separator, but both Gemini semantic rows timed out; repeat Gemini only after semantic route health is fixed |
| owner/orchestration compactness needs repeat evidence | complete for X3 versus X1 on single-session recovery packets, now including explicit low-noise operator budget via N56, and complete for X1 versus X3 on staged owner packets; repeat only if deciding between X3 and X5 after X5 quota/route health returns or if a real repo owner workflow is admitted |

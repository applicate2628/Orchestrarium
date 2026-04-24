# Hardening Wave Roadmap

Date: 2026-04-22
Owner: `$lead`
Status: `ACTIVE`

## Purpose

Keep the next X1/X3 lane-fit hardening cycles grouped into explicit waves instead of ad-hoc
single-scenario pushes. This roadmap is the live control surface for subsequent diagnostic
scenarios after `N20`.

## Current Admission Source

Direct human instruction: continue benchmark hardening, split subsequent cycles into waves, maintain
a roadmap, and use spawns when that accelerates independent work.

## Operating Rules

| Rule | Contract |
|---|---|
| one live roadmap | update this file in place; do not create competing stale roadmaps |
| result source of truth | classify from `summary.json`, verifier logs, and scorer JSON, not noisy stdout |
| top-pair runs | every admitted wave runs `X1` and `X3` first |
| calibration rows | run `X2`, `X5`, and `X6` only after global/lane-relevant changes; `X5` still requires a same-session smoke that writes output |
| route failures | keep quota, wrapper timeout, missing summary, and Gemini tool-loop failures separate from model FAIL |
| X4 | keep `NOT-RUN` until the secret-backed Claude route stops returning provider errors |
| write scope | main agent owns roadmap, scenario materialization, scorers, live result surfaces, and session logs |
| spawn scope | spawned agents may do read-only design/recon or disjoint implementation slices only when explicitly assigned |
| closeout | each admitted wave updates `x1-mainline-hardening-no-new-failures-2026-04-21.md`, role-fit scorecard, short results, status checkpoint, scorer JSON, and `.reports/2026-04/` |

## Wave Queue

| Wave | Status | Primary Question | Candidate Scenario | Owner | Spawn Plan | Gate |
|---|---|---|---|---|---|---|
| `W0` completed baseline | `DONE` | Which lanes already have routing-grade evidence? | `N16..N20` | `$lead` | none now; complete | `PASS`: role-fit scorecard updated through `E10` |
| `W1` visual provider fit | `DONE` | Is Gemini actually better for visual/graphics work, or only policy-preferred? | `E11 / N21` visual asset or graphics-state rubric | `$graphics-engineer` + `$ui-test-engineer` style verifier | visual explorer proposal accepted and materialized | `X1`, `X2`, and `X3` scoreable PASS; `X3 100`, `X1 89`, `X2 85`; Gemini rows runtime no-summary after launch |
| `W2` hard numerical constraints | `DONE` | Can X1/X3 separate on algorithmic/numerical reasoning beyond N18? | `E12 / N22` numerical stability constraint gauntlet | `$algorithm-scientist` or `$computational-scientist` | numerical explorer proposal accepted and materialized | `X1` and `X3` both pass; `X2` scoreably fails; `X6` route-fails |
| `W3` owner recovery under stale-source traps | `DONE` | Does a longer recovery/routing packet split owner/orchestration style or correctness? | `E13 / N23` owner recovery packet | `$lead` with `$knowledge-archivist` constraints | owner explorer proposal accepted and materialized | `X1` and `X3` both pass; scored read favors `X3 100` over `X1 90` |
| `W4` repeat-confirmation | `DONE` | Are N19/N20/N23/N21 X3 edges stable enough for routing policy? | `N24` systems/toolchain repeat; `N25` UI dirty-state repeat | matching implementation owner | repeat-confirmation spawn completed candidate table; post-N25 sidecar proposed next waves | `N24` confirms systems/toolchain `X3 primary`; `N25` confirms UI `X3 > X1` and identifies route-healthy `X5` as a UI contender |
| `W5` scoring normalization | `DONE` | Should rubric scores be normalized across N16/N19/N20/N21/N22/N23 before stronger claims? | scorer-only analysis, no model run | `$qa-engineer` / `$analyst` | scorer-normalization spawn completed memo | compactness-only single-run winners downgraded to `provisional-primary` |
| `W6` owner repeat-confirmation | `DONE` | Is the N23 owner recovery edge stable enough for owner-routing policy? | `E16 / N26` owner recovery wave roadmap reconciliation | `$lead` | post-N25 sidecar proposal accepted and materialized | `X1`, `X3`, and `X5` pass; `X3 100`, `X5 100`, `X1 92`; `X2` and `X6` scoreable `FAIL` |
| `W7` long-horizon repeat | `DONE` | Does the N16 long-horizon integration edge repeat on a new domain? | `E17 / N27` release train governor repeat | `$backend-engineer` / `$platform-engineer` style verifier | N27 scorer/verifier sidecar caught anti-hardcoding gap before launch | `X1`, `X2`, and `X3` pass; `X3 92`, `X1 88`, `X2 88`; `X6 ROUTE-FAIL`; `X5 REQUEUE` after failed smoke |
| `W8` cross-role incident repair | `DONE` | Does adding incident source arbitration, stale requirements, review response, tests, and final reconciliation finally split X1/X3? | `E18 / N28` incident-driven integration repair | `$backend-engineer` plus review/reconciliation gate | N28 read-only sidecar accepted verifier/scorer gate before launch | `X1` and `X3` pass; `X3 99`, `X1 93`; `X2 scoreable FAIL 16`; `X6 ROUTE-FAIL`; `X5 REQUEUE` after smoke timeouts |
| `W9` ownership-budget incident repair | `DONE` | Does a near-pass localized repair plus exact patch-budget gate split X1/X3? | `E19 / N29` ownership-budget incident repair | `$backend-engineer` plus machine-ledger/scope gate | N29 read-only sidecar recommended near-pass semantic budget design | `X1` and `X3` pass exact four-path budget; `X3 100`, `X1 96`; `X2 scoreable FAIL 42`; `X6 RUNTIME-FAIL`; `X5 REQUEUE` |
| `W10` staged delivery re-entry | `DONE` | Does a real multi-invocation staged runner split X1/X3 on persisted phase state and re-entry? | `E20 / N30` staged delivery re-entry | `$lead` integration-owner simulation plus implementation verifier | W10 sidecar accepted only if staged runner exists; materialized as four fresh invocations over one run root | `X1 PASS 96`; `X3 scoreable FAIL 91` after omitting one phase ledger; `X2 scoreable FAIL 66`; `X6 RUNTIME-FAIL`; `X5 REQUEUE` |
| `W11` scientific computation hardening | `DONE` | Can a real physics analytical-oracle numerical task split X1/X3? | `E21 / N31` MoM PEC-cylinder analytical oracle | `$computational-scientist` / `$algorithm-scientist` style verifier | MoM design superseded easier textbook-potential draft before commit | `X1` and `X3` both pass; `X3 94`, `X1 92`; binary tie remains, but N31 upgrades the lane to real CEM/MoM evidence |
| `W12` scientific computation repeat | `DONE` | Can a combined real-physics task with MoM plus hydrogenic radial Schrodinger and solver-runtime scoring split the top pair? | `E22 / N32` dual-physics analytical oracle | `$computational-scientist` plus `$performance-engineer` style verifier | no spawn; mainline materialization | `X1` and `X3` both pass; `X3 100`, `X1 97`; `X2` scoreable FAIL 33; `X6` runtime no-summary; `X5` smoke REQUEUE |
| `W13` interface refactor breakage | `DONE` | Does a structured interface refactor with hidden consumers split X1/X3 on call-site migration and compatibility preservation? | `E23 / N33` interface refactor breakage gauntlet | `$backend-engineer` style verifier plus hidden consumer gate | no active spawn; mainline materialization | `X1` and `X3` both pass; `X3 100`, `X1 96`; `X2` scoreable FAIL 5; `X6` runtime no-summary |
| `W14` high-load scientific performance | `DONE` | Does staged high-load CEM plus radial Schrodinger performance expose runtime/patch-quality differences after N32 tied? | `E24 / N34` high-load science optimizer | `$computational-scientist` / `$performance-engineer` | one worker was stopped after write-race; mainline integration completed | `X1` and `X3` both pass and both read 96; X1 is faster on solver metrics, X3 is much more compact; `X2` scoreable FAIL 27 |
| `W15` staged interface migration | `DONE` | Does combining interface refactor breakage with four fresh invocations split X1/X3? | `E25 / N35` staged interface migration re-entry | `$backend-engineer` plus staged re-entry verifier | no active spawn; mainline materialization | `X1 PASS 96`; `X3 scoreable FAIL 71`; `X2 PASS 91`; Gemini rows route-fail |
| `W16` real-repo staged API migration | `DONE` | Does the staged migration split repeat on a fresh BillingMesh-style API domain? | `E26 / N36` real-repo staged API migration | `$backend-engineer` plus staged re-entry verifier | no active spawn; mainline materialization | `X1 PASS 97`; `X3 scoreable FAIL 74`; `X2 scoreable FAIL 70`; X6 runtime no-summary; X5 smoke-gated |
| `W17` staged adversarial review gate | `DONE` | Does the staged/re-entry split also apply to advisory architecture and review-gate lanes? | `E27 / N37` staged adversarial review gate | `$architecture-reviewer` / `$qa-engineer` style verifier plus staged response gate | read-only sidecar recommended review/advisory staged gauntlet; mainline materialization | `X1 PASS 98`; `X3 scoreable FAIL 35`; `X2 PASS 97`; `X6 ROUTE-FAIL`; `X5` smoke timeout |
| `W18` staged UI/visual/state integration | `DONE` | Does the staged/re-entry split apply to UI implementation when state, ARIA, layout, and raster pixels must stay coherent together? | `E28 / N38` deterministic UI/visual/state integration | `$frontend-engineer` plus `$visualization-engineer` style verifier | read-only sidecar recommended N38; mainline materialized and reference-validated | `X1 PASS 94`; `X2 FAIL 78`; `X3` repeated runtime no-summary after three attempts; `X5/X6` route caveats; not a top-pair semantic separator |
| `W19` staged systems/toolchain recovery re-entry | `DONE` | Does the systems/toolchain `X3 primary` single-shot edge survive staged fresh invocations, recovery source arbitration, runtime-status discipline, ledger, and bounded closeout? | `E29 / N39` staged systems/toolchain reentry | `$toolchain-engineer` plus staged re-entry and recovery verifier | mainline materialized from N24 and hardened with N23/N26-style stale-source and owner-continuity traps; bounded-scope redesign removed exact-scope artifact | `X1 PASS 94`; `X3 scoreable FAIL 78`; `X2 FAIL 76`; `X6 FAIL 78`; `X5` route-fail; staged systems/toolchain now reads `X1 primary` |
| `W20` staged owner recovery re-entry | `DONE` | Does the owner-recovery `X3 primary` single-shot edge survive staged source recovery, runtime policy, and closeout? | `E30 / N40` staged owner recovery reentry | `$lead` owner-recovery verifier | mainline materialized while X3 quota was unavailable | `X1 PASS 98`; `X3 FAIL 55`; `X2 FAIL 78`; `X6 FAIL 40`; `X5` route-fail; staged owner recovery now reads `X1 primary` |
| `W21` staged incident-budget re-entry | `DONE` | Does the long-horizon/cross-role/ownership-budget `X3 primary` single-shot edge survive staged runtime repair, repair ledger, exact patch budget, and closeout? | `E31 / N41` staged incident-budget reentry | `$backend-engineer` plus staged re-entry and patch-budget verifier | mainline materialized while X3 quota was unavailable | `X1 PASS 100`; `X3 FAIL 78`; `X2 FAIL 78`; `X5` route-fail; `X6` no-summary; staged incident-budget re-entry now reads `X1 primary` |
| `W22` systems immutable-CI inverse probe | `DONE` | Can the compact systems/toolchain `X3` edge become an honest `X1 FAIL / X3 PASS` if visible tests are immutable and only production files may change? | `E32 / N42` systems/toolchain immutable-CI hotfix | `$toolchain-engineer` style verifier plus protected visible-test hash | mainline materialized from N24 with immutable test scope | `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass; `binary tie remains`; no inverse separator |
| `W23` UI immutable-test inverse probe | `DONE` | Can the compact UI `X3` edge become an honest `X1 FAIL / X3 PASS` if visible tests are immutable and only UI production files may change? | `E33 / N43` UI dirty-state immutable-test hotfix | `$frontend-engineer` style verifier plus protected visible-test hash | mainline materialized from N25 with immutable test scope | `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass; `binary tie remains`; no inverse separator |
| `W24` interface sourceId hidden consumer | `DONE` | Can a hidden public-result consumer expose interface-refactor breakage, and can it find the requested inverse separator? | `E34 / N44` interface-refactor sourceId hidden consumer | `$backend-engineer` style verifier plus hidden consumer and exact scope gate | mainline materialized from N33 with immutable visible test and sourceId/report invariant | `X1 PASS 96`; `X3 scoreable FAIL 72` from `.pytest_cache` changed-path drift; not an inverse separator and not a hidden sourceId semantic fail |
| `W25` ownership-budget immutable report consumer | `QUEUED` | Can the compact single-session ownership-budget `X3` edge become an honest `X1 FAIL / X3 PASS` when visible tests are immutable and a hidden public report consumer checks replay/source semantics? | `E35 / N45` ownership-budget immutable report consumer | `$backend-engineer` style verifier plus protected visible-test hash, hidden replay gate, and report-consumer gate | read-only W25 sidecar recommended N29-derived probe as least-bad remaining inverse candidate | materialize after current commit; avoid exact-scope brittleness that would only reproduce N44 hygiene noise |

## Active Spawn Board

| Spawn | Scope | Write Access | Expected Artifact | Status |
|---|---|---|---|---|
| visual explorer | inspect `S22/S23/S24`, scorecard, and N19/N20 patterns | none | proposal for `W1 / N21` | `DONE`; proposal accepted as queued input |
| numerical explorer | inspect `S10..S14`, N18, scorecard | none | proposal for `W2 / N22` | `DONE`; proposal admitted for next materialization |
| owner explorer | inspect N17 and owner/recovery evidence | none | proposal for `W3 / N23` | `DONE`; proposal accepted as queued input |
| repeat-confirmation explorer | inspect N19/N20/N23/N21 scorecard and evidence | none | candidate table for W4 repeats | `DONE`; `N24` systems/toolchain repeat admitted first |
| scorer-normalization auditor | inspect N16..N23 scorer comparability | none | scorer-normalization memo | `DONE`; scorecard now uses `provisional-primary` for compactness-only edges |
| post-N25 roadmap sidecar | inspect N24/N25 closeout direction and remaining lane needs | none | next-wave ordering proposal | `DONE`; recommended `N26` owner-recovery repeat before long-horizon expansion when owner policy matters |
| N27 scorer/verifier sidecar | inspect N27 contract/verifier/scorer patterns | none | scorer field proposal and verifier consistency gate | `DONE`; anti-hardcoding coverage REVISE accepted before X1/X3 launch |
| N28 cross-role gate sidecar | inspect N28 contract/verifier/scorer after materialization | none | gate verdict and risk note | `DONE`; accepted as cross-role gate, with caveat that reconciliation note checks are substring-based |
| N29 ownership-budget sidecar | inspect W9 route and N29 risks | none | semantic budget design memo | `DONE`; recommended near-pass baseline, structured ledger, and exact changed-path budget |
| W17 review-gate sidecar | inspect remaining lane gaps after N36 | none | next-wave ordering proposal | `DONE`; recommended staged ADR/review gate first, then UX and harder numerical repeats |
| W18 UI/visual sidecar | inspect N20/N21/N25 UI and visual patterns | none | deterministic UI/visual/state gauntlet proposal | `DONE`; N38 materialized and reference-validated |
| W19 next-lane sidecar | inspect N19/N24 and N23/N26 for next staged target | none | next staged gauntlet proposal | `DONE`; N39 materialized as staged systems/toolchain recovery candidate and later rerun under bounded scope |

## Spawn Proposal Results

| Wave | Proposed Scenario | Useful Signal | Admission Read |
|---|---|---|---|
| `W1 / E11` | `N21-visual-provider-fit-raster-gauntlet` | deterministic raster oracle for transparent gaps, focus layering, legend order, annotation pixels, and PPM metadata | `DONE`; binary correctness tied X1/X3, X3 won rubric by compactness/cost, Gemini preference not proven because X5/X6 timed out after launch |
| `W2 / E12` | `N22-numerical-stability-constraint-gauntlet` | exact numerical witnesses for p95, variance, shard merge, memory bounds, and stale benchmark rejection | `DONE`; binary tie remained (`X1 PASS`, `X3 PASS`), scored read `X1 100`, `X3 99`, `X2 FAIL`, `X6 ROUTE-FAIL` |
| `W3 / E13` | `N23-owner-recovery-stale-source-routing-gauntlet` | recovery/source-of-truth discrimination under stale leaderboard, diagnostic-promotion, owner-route, and calibration traps | `DONE`; useful owner-lane scored split: `X3 100`, `X1 90`, `X2 FAIL`, `X6 ROUTE-FAIL` |
| `W4 / E14` | `N24-systems-toolchain-staging-repeat` | repeat N19-style path/cache/fingerprint/lease semantics before making systems/toolchain `X3` a hard primary | `DONE`; `X1 PASS 86`, `X3 PASS 95`; `X2`, `X5`, and `X6` scoreable `FAIL`; `X5` admitted after same-session smoke-output |
| `W4 / E15` | `N25-ui-dirty-state-navigation-guard-gauntlet` | repeat N20-style UI implementation on dirty-state, navigation guards, validation, failed-save rollback, focus, and status rendering | `DONE`; `X5 PASS 98`, `X3 PASS 97`, `X1 PASS 86`, `X2 scoreable FAIL 43`, `X6 ROUTE-FAIL`; UI policy now reads `X3 primary` versus `X1`, with `X5` a route-healthy contender pending one more UI-family pass |
| `W5` | scorer-normalization memo | compare semantic versus efficiency points before cross-lane claims | `DONE`; current scorecard marks compactness/output edges as `provisional-primary` |
| `W6 / E16` | `N26-owner-recovery-wave-roadmap-reconciliation-gauntlet` | repeat N23-style owner recovery after N24/N25 changed live lane state; includes denominator, spawn, X5-contender, and stale-file traps | `DONE`; `X3 PASS 100`, `X5 PASS 100`, `X1 PASS 92`, `X2 scoreable FAIL 70`, `X6 scoreable FAIL 50`; owner policy now reads `X3 primary` versus `X1`, with `X5` an owner contender pending another owner-family pass |
| `W7 / E17` | `N27-release-train-governor-long-horizon-repeat-gauntlet` | repeat N16 long-horizon integration on a new deploygrid domain: profile precedence, dedupe, dependencies, canary/prod, freeze, resume, rollback, and audit/report trace | `DONE`; `X3 PASS 92`, `X1 PASS 88`, `X2 PASS 88`, `X6 ROUTE-FAIL`; `X5 REQUEUE` because same-session smoke hit quota |
| `W8 / E18` | `N28-incident-driven-integration-repair-gauntlet` | extend N27 into cross-role incident repair: runtime patch, source arbitration, stale-source rejection, review response, tests, and final reconciliation | `DONE`; `X3 PASS 99`, `X1 PASS 93`, `X2 scoreable FAIL 16`, `X6 ROUTE-FAIL`; `X5 REQUEUE` because same-session smoke timed out |
| `W9 / E19` | `N29-ownership-budget-incident-repair-gauntlet` | start from a near-pass deploy runtime and require a localized runtime fix, tests, structured source/review/validation ledger, and exact four-path patch budget | `DONE`; `X3 PASS 100`, `X1 PASS 96`, `X2 scoreable FAIL 42`, `X6 RUNTIME-FAIL`; `X5 REQUEUE` because smoke timed out |
| `W10 / E20` | `N30-staged-delivery-reentry-gauntlet` | first staged runner: four fresh provider invocations over one copied bundle, requiring persisted plan, implementation, review response, and closeout state | `DONE`; first current top-pair binary separator: `X1 PASS 96`, `X3 scoreable FAIL 91`; `X2` scoreable FAIL; Gemini rows runtime caveats |
| `W11 / E21` | `N31-mom-cylinder-analytic-oracle` | harden generic numerical reasoning with real computational electromagnetics: Method of Moments PEC-cylinder solve against cylindrical-harmonic analytical oracle | `DONE`; `X1` and `X3` both pass; `X3 94`, `X1 92`; binary tie remains |
| `W12 / E22` | `N32-dual-physics-analytic-oracle` | combine strengthened MoM PEC-cylinder analytical oracle with hydrogenic radial Schrodinger finite-difference analytical oracle and score measured solver runtime | `DONE`; `X1` and `X3` both pass; `X3 100`, `X1 97`; `X2` scoreable FAIL 33; `X6` runtime no-summary; `X5` smoke REQUEUE |
| `W13 / E23` | `N33-interface-refactor-breakage-gauntlet` | test interface-refactor fragility through structured result objects, hidden consumers, legacy wrapper removal, migration ledger, and exact patch scope | `DONE`; `X1` and `X3` both pass; `X3 100`, `X1 96`; `X2` scoreable FAIL 5; `X6` runtime no-summary |
| `W14 / E24` | `N34-high-load-science-optimizer-gauntlet` | combine staged re-entry, high-load MoM PEC-cylinder cases, hydrogenic radial grids, runtime scoring, perf ledger, and optimization report | `DONE`; `X1` and `X3` both pass and both read 96; X1 faster, X3 much more compact; `X2` scoreable FAIL 27 |
| `W15 / E25` | `N35-staged-interface-migration-reentry-gauntlet` | combine N33 interface migration with N30 staged runner: persisted plan, implementation, review response, closeout, hidden consumers, exact scope | `DONE`; `X1 PASS 96`, `X3 scoreable FAIL 71`, `X2 PASS 91`; Gemini rows route-fail |
| `W16 / E26` | `N36-realrepo-staged-api-migration-gauntlet` | repeat N35 on a real-repo-style BillingMesh API migration: account lookup, entitlement policy, usage publisher, service/API/reporting consumers, review response, exact scope | `DONE`; `X1 PASS 97`, `X3 scoreable FAIL 74`, `X2 scoreable FAIL 70`; `X6` runtime no-summary; `X5` smoke-gated |
| `W17 / E27` | `N37-staged-adversarial-review-gate-gauntlet` | extend the staged separator into advisory/review: source ledger, source-bound ADR, exact findings, false-positive rejection, response gate, and closure | `DONE`; `X1 PASS 98`, `X3 scoreable FAIL 35`, `X2 PASS 97`; `X6 ROUTE-FAIL`; `X5` smoke timeout |
| `W18 / E28` | `N38-deterministic-ui-visual-state-integration-gauntlet` | combine N20 UI state, N25 dirty-state/accessibility, and N21 deterministic raster pixels into one staged UI/visual/state integration task | `DONE`; pre-run gates passed; `X1 PASS 94`, `X2 FAIL 78`, `X3` repeated no-summary runtime stall across three attempts, `X5/X6` route caveats; useful X1 evidence but not a scoreable top-pair separator |
| `W19 / E29` | `N39-staged-systems-toolchain-reentry-gauntlet` | convert N24 systems/toolchain staging into a four-phase re-entry task with N23/N26-style stale-source recovery, runtime-status discipline, implementation ledger, closeout, bounded scope, and functional toolchain oracle | `DONE`; bounded-scope rerun passed pre-run gates and produced `X1 PASS 94` versus `X3 scoreable FAIL 78`; staged systems/toolchain recovery is now an X1-over-X3 separator |
| `W20 / E30` | `N40-staged-owner-recovery-reentry-gauntlet` | convert owner recovery into a four-phase source-ledger, route-decision, runtime-policy, and closeout packet | `DONE`; pre-run gates passed; `X1 PASS 98`, `X3 FAIL 55`, `X2 FAIL 78`, `X6 FAIL 40`, `X5` route-fail; staged owner recovery becomes an X1 lane |
| `W21 / E31` | `N41-staged-incident-budget-reentry-gauntlet` | convert the N28/N29 DeployGrid incident repair family into a four-phase staged runtime repair, repair ledger, reentry state, exact six-path budget, and closeout | `DONE`; pre-run gates passed; `X1 PASS 100`, `X3 FAIL 78`, `X2 FAIL 78`, `X5` route-fail, `X6` no-summary; staged incident-budget re-entry becomes an X1 lane |
| `W22 / E32` | `N42-systems-toolchain-immutable-ci-hotfix` | protect the visible test by hash and force production-only stagegate repair to test whether X1 over-edits when tests are immutable | `DONE`; `X1` and `X3` both pass; `binary tie remains`; no inverse separator |
| `W23 / E33` | `N43-ui-dirty-state-immutable-test-hotfix` | protect the visible UI test by hash and force production-only dirty-state repair to test whether X1 over-edits when tests are immutable | `DONE`; `X1` and `X3` both pass; `binary tie remains`; no inverse separator |
| `W24 / E34` | `N44-interface-refactor-sourceid-hidden-consumer` | extend single-shot interface refactor with hidden public `sourceIds` consumer, report aggregation, immutable visible test, and exact nine-path budget | `DONE`; `X1 PASS 96`; `X3 FAIL 72` only because `.pytest_cache` files violated exact changed-path scope; hidden sourceId semantics pass for X3 |
| `W25 / E35` | `N45-ownership-budget-immutable-report-consumer` | derive from N29: protect visible test by hash, remove test edits from patch budget, keep production/ledger repair, add hidden double-run replay and public report-consumer checks | `QUEUED`; admitted as next inverse probe because N29 remains an X3-primary single-session lane and this exact frozen-test/report-consumer variant has not been tested |

## Current Admission Decision

`W4 / N24`, `W4 / N25`, and `W6..W24 / N26..N44` are now complete. The staged follow-up batch
closed four queued rows in one pass: `N38` is useful positive X1 evidence but unresolved for the
top pair because X3 never produced a scoreable final summary; bounded `N39`, `N40`, and `N41` are
scoreable top-pair separators in favor of X1. Follow-up inverse probes `N42` and `N43` tied top pair
under immutable visible-test constraints; `N44` went in the opposite direction, producing X1-over-X3
patch-hygiene separation rather than the requested `X1 FAIL / X3 PASS` line.

Reason: `N19` and `N24` independently read `X3 95 / 100` versus `X1 86 / 100`, with both top
pair rows passing the binary verifier and calibration rows separating lower. This moves
systems/toolchain from `X3 provisional-primary` to `X3 primary` for compact path/cache/fingerprint
and lease-lifecycle patches.

`N20` and `N25` now independently read `X3 > X1` on UI implementation. `N25` also produced a
route-healthy `X5 PASS 98 / 100`, narrowly above `X3 PASS 97 / 100`, so `X5` is a real UI contender
but needs one more UI-family pass before it can displace `X3` as the general UI default.

`N23` and `N26` now independently read `X3 > X1` on owner recovery. `N26` also produced a
route-healthy `X5 PASS 100 / 100`, tying `X3 PASS 100 / 100`, so `X5` is a real owner-recovery
contender but needs another owner-family pass before it can displace `X3`.

`N16` and `N27` independently read `X3 > X1` on compact long-horizon integration, `N28` extends
that signal into cross-role incident repair, and `N29` confirms that even near-pass ownership-budget
repairs with an exact changed-path gate do not binary-split the top pair. `N30` then changes the
execution shape rather than the domain: four fresh invocations over one run root. That produces the
first current top-pair binary separator, `X1 PASS` versus `X3 scoreable FAIL`, because X3 omitted the
`03-review-response` persisted phase ledger. Current policy split: `X3 primary` for compact
single-session long-horizon/cross-role implementation, `X1 primary` for staged delivery re-entry and
phase-ledger accountability.

W11 added a scientific computation hardening wave to the generic numerical reasoning lane. The
admitted task is computational electromagnetics rather than a textbook potential: Method of Moments
for a PEC circular cylinder, with the exact cylindrical-harmonic series as analytical oracle. Both
top-pair rows pass; the lane gains real physics evidence but not a binary separator.

W12 combines the previously discussed scientific hardening ideas into one task: MoM PEC-cylinder
surface-density/field checks plus hydrogenic radial Schrodinger finite-difference checks, both with
analytical oracles and measured solver-runtime scoring. `X1` and `X3` both pass; the scientific lane
still has no top-pair binary separator, but `X2` separates lower scoreably and Gemini rows remain
route/runtime caveats.

W13 tests the user's interface-refactor hypothesis directly as a single-shot task. It separates
`X2` lower scoreably but does not split the top pair. W14 combines staged state plus high-load
scientific performance; it ties by binary but exposes a useful non-binary tradeoff: `X1` is faster
on measured solver runtime while `X3` is much more compact. W15 then combines the interface
migration hypothesis with the staged runner and produces a second top-pair binary separator:
`X1 PASS` versus `X3 scoreable FAIL`. W16 repeats that split on a fresh BillingMesh-style API
migration, so staged API/interface migration is now confirmed as an `X1 primary` lane.

W17 extends the staged/re-entry hypothesis outside implementation into advisory architecture and
review-gate work. `N37` is a scoreable top-pair split: `X1 PASS 98 / 100` versus `X3 FAIL 35 / 100`.
X3 completed the wrapper and changed the required files, but missed ADR source binding, exact
finding/source-id tuples, non-claim markers, response cues, and closure validation. This promotes
`X1 primary` for staged source arbitration, ADR traceability, response-gate closure, and exact
review ledgers; ordinary single-shot tuple-exact review remains an `X1/X3` near-tie.

W18 tested the same staged hypothesis on UI/visual/state integration. `X1` passed at `94 / 100`,
but X3 stalled without a final `summary.json` across three attempts, so the row does not currently
separate the top pair semantically. W19 tested staged systems/toolchain recovery. The initial exact
scope was too tight, but the bounded-scope rerun removed that artifact and produced `X1 PASS
94 / 100` versus `X3 scoreable FAIL 78 / 100`.

W19, W20, and W21 are the important routing changes. W19 turns systems/toolchain recovery into a
staged packet and produces `X1 PASS 94 / 100` versus `X3 FAIL 78 / 100`. W20 turns owner recovery
into a staged packet and produces `X1 PASS 98 / 100` versus `X3 FAIL 55 / 100`. W21 turns the
incident-budget family into a staged repair-ledger/reentry-state/closeout packet and produces
`X1 PASS 100 / 100` versus `X3 FAIL 78 / 100`. Current policy split is now explicit by execution
shape: `X3 primary` for compact single-session systems/toolchain, owner, and incident repair
packets; `X1 primary` for staged systems recovery, staged owner, and staged incident-budget
re-entry.

W22 and W23 tested the most plausible inverse path directly: protect visible tests and make the
task production-only. Both tied by binary, so immutable visible tests alone do not produce an honest
`X1 FAIL / X3 PASS` on systems/toolchain or UI. W24 tested hidden interface consumer preservation;
it also did not produce the requested inverse separator. It adds an X1-over-X3 patch-hygiene signal
because X3 left `.pytest_cache` files inside the exact changed-path budget while preserving hidden
sourceId semantics.

W25 is admitted as the next inverse probe before more staged expansions. It should be N29-derived,
single-session, and production/ledger-only: protect the visible test by hash, keep the repair tied to
the public API/report contract, add hidden double-run replay and report-consumer checks, and avoid
using raw transcript size or `.pytest_cache` drift as the semantic signal.

## Execution Order

1. Collect read-only spawn proposals for `W1..W3`. `DONE` on 2026-04-22.
2. Admit the highest-yield wave using this priority:
   - likely to change routing policy
   - executable verifier available without brittle external services
   - start-state failure set is precise
   - calibration rows can run without known route hangs
3. Materialize `W1 / N21` scenario and scorer. `DONE` on 2026-04-22.
4. Validate:
   - JSON parse
   - `--bundle-shape-only`
   - `--expect-start-state`
   - scratch reference solution passes verifier and local checks
   - `git diff --check`
5. Run:
   - `X1` via `cmd /c "pwsh ... < NUL"`
   - `X3` direct PowerShell runner
   - `X2`/`X6` when useful
   - `X5` only after a direct smoke writes output
6. Score and update live surfaces in place.
7. Re-rank the wave queue; continue while results are useful.
8. Materialize `W4 / N24` as a systems/toolchain repeat before hardening `X3` from provisional to hard primary. `DONE` on 2026-04-22.
9. Materialize `N25` as a UI dirty-state/navigation guard repeat. `DONE` on 2026-04-22.
10. Materialize `N26-owner-recovery-repeat`. `DONE` on 2026-04-22.
11. Materialize `N27-long-horizon-integration-repeat`. `DONE` on 2026-04-22.
12. Materialize `N28-cross-role-incident-repair`. `DONE` on 2026-04-22.
13. Materialize `N29-ownership-budget-incident-repair`. `DONE` on 2026-04-23.
14. Materialize `N30-staged-delivery-reentry` with staged runner and time/cost/patch-quality scoring. `DONE` on 2026-04-23.
15. Materialize `N31-mom-cylinder-analytic-oracle` as W11/E21. `DONE` on 2026-04-23.
16. Materialize `N32-dual-physics-analytic-oracle` as W12/E22. `DONE` on 2026-04-23.
17. Materialize `N33-interface-refactor-breakage-gauntlet` as W13/E23. `DONE` on 2026-04-23.
18. Materialize `N34-high-load-science-optimizer-gauntlet` as W14/E24. `DONE` on 2026-04-23.
19. Materialize `N35-staged-interface-migration-reentry-gauntlet` as W15/E25. `DONE` on 2026-04-23.
20. Materialize `N36-realrepo-staged-api-migration-gauntlet` as W16/E26. `DONE` on 2026-04-23.
21. Materialize `N37-staged-adversarial-review-gate-gauntlet` as W17/E27. `DONE` on 2026-04-23.
22. Materialize `N38-deterministic-ui-visual-state-integration-gauntlet` as W18/E28. `DONE` on 2026-04-23.
23. Materialize `N39-staged-systems-toolchain-reentry-gauntlet` as W19/E29 with recovery source-arbitration hardening and bounded-scope rerun. `DONE` on 2026-04-23.
24. Materialize `N40-staged-owner-recovery-reentry-gauntlet` as W20/E30. `DONE` on 2026-04-23.
25. Materialize `N41-staged-incident-budget-reentry-gauntlet` as W21/E31. `DONE` on 2026-04-23.
26. Run `N38,N39,N40,N41` on `X1` and `X3`, then add `X2`, `X5`, and `X6` as calibration rows where routes are healthy. `DONE` on 2026-04-23; honest results: `N38` unresolved because X3 had repeated no-summary runtime stalls; bounded `N39`, `N40`, and `N41` are X1 separators.
27. Materialize immutable visible-test inverse probes `N42` and `N43`. `DONE` on 2026-04-24; both tied `X1` and `X3` by binary gate.
28. Materialize hidden interface-consumer inverse probe `N44`. `DONE` on 2026-04-24; X1 passed, X3 failed exact patch hygiene, not hidden sourceId semantics.
29. Materialize `N45-ownership-budget-immutable-report-consumer` as W25/E35. `NEXT`; use N29 as the source family, preserve single-session execution, and run X1/X3 first before any calibration rows.

## Current Routing Impact

| Lane | Current Read | Next Need |
|---|---|---|
| long-horizon / cross-role / ownership-budget integration | split by execution shape: `X3 primary` for compact single-session integration and incident repair after `N16`, `N27`, `N28`, and `N29`; `X1 primary` for staged incident-budget re-entry after `N41 PASS 100` versus `X3 FAIL 78` | W25/N45 is the admitted exception: one inverse probe on N29 with immutable visible tests plus hidden public report consumer |
| staged delivery / multi-session re-entry | `X1 primary` after `N30`, `N35`, and `N36` produced `X1 PASS` versus `X3 scoreable FAIL` on persisted phase-ledger / re-entry accountability | strong enough for staged-lane routing; next repeat should be a real repo trial, not another synthetic bundle |
| staged review / advisory gate | `X1 primary` after `N37` produced `X1 PASS 98 / 100` versus `X3 scoreable FAIL 35 / 100` on source-bound ADR, exact findings/non-claims, response cues, and closure | strong enough for staged review-gate routing; next repeat should be a real repo review trial or a UX/visual lane where policy remains unresolved |
| systems/toolchain | `X3` primary after `N19` and `N24` both read `95 / 100` versus `X1 86 / 100`; `N42` confirms immutable visible-test constraints still tie top pair by binary; `X2/X5/X6` lower on N24 | no immediate repeat needed unless a new systems subdomain becomes policy-critical |
| systems/toolchain staged recovery re-entry | `X1 primary` after bounded `N39` produced `X1 PASS 94 / 100` versus `X3 FAIL 78 / 100`; `X2` and `X6` also fail scoreably and `X5` is route-fail | strong enough for staged systems/toolchain routing; next repeat should be a real repo toolchain workflow only if policy needs extra confirmation |
| UI implementation | `X3` primary versus `X1` after `N20` and `N25`; `N43` confirms immutable visible-test constraints still tie top pair by binary; `X5` is still a route-healthy contender after `N25 PASS 98`; `N38` adds an `X1` staged UI pass but leaves the top pair unresolved because X3 never completed scoreably | if staged UI policy matters, rerun N38 under a more reliable X3 wrapper/timeout strategy; otherwise keep the single-session UI read |
| owner recovery staged re-entry | `X1 primary` after `N40` produced `X1 PASS 98 / 100` versus `X3 FAIL 55 / 100` | strong enough for staged owner routing; next repeat should be a real repo owner workflow only if policy needs extra confirmation |
| incident-budget staged re-entry | `X1 primary` after `N41` produced `X1 PASS 100 / 100` versus `X3 FAIL 78 / 100` | strong enough for staged incident-budget routing; next repeat should be a real repo repair workflow only if policy needs extra confirmation |
| scientist/constraints | `X1/X3` correctness tie on `N18`, `N22`, `N31`, `N32`, and `N34`; N31 adds real CEM/MoM evidence, N32 combines MoM with hydrogenic radial Schrodinger, and N34 adds high-load staged performance; `X1` is faster on N34, `X3` is more compact | co-primary; choose X1 for runtime-sensitive scientific solver work and X3 for compact output |
| interface refactor / migration | single-shot `N33` ties and favors X3 compactness; `N44` adds an X1-over-X3 exact patch-hygiene signal while hidden sourceId semantics tie; staged `N35` and `N36` split `X1 PASS` versus `X3 scoreable FAIL` | route staged API/interface migrations to X1; keep X3 for compact single-session refactors unless exact patch budget hygiene is the dominant risk |
| owner/orchestration | `X3` primary versus `X1` after `N23` and `N26`; `X5` is a route-healthy owner contender after `N26 PASS 100`, but needs another owner-family pass before policy promotion | one more owner-family `X5` check only if deciding between `X3` and `X5`; otherwise move to long-horizon repeat |
| visual/graphics | geometry tied on `S22`; `N21` ties X1/X3 on visual correctness and favors X3 on compactness; Gemini preference not proven | repeat only after Gemini semantic route health is fixed |

## Resume Point

Resume from this roadmap plus:

- `Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md`
- `Work/next-upgraded-pack/Checkpoints/status-2026-04-16.md`
- latest scorer JSON under `Work/next-upgraded-pack/Evidence/`

If interrupted now, resume from the scored `N42..N44` inverse-probe closeout rather than from a queued batch.
Single-session systems/toolchain, UI implementation, owner recovery, compact long-horizon
integration, cross-role incident repair, and ownership-budget repair still read `X3 primary`
versus `X1`. Staged delivery (`N30`, `N35`, `N36`), staged review (`N37`), staged owner recovery
(`N40`), and staged incident-budget re-entry (`N41`) now all read `X1 primary` versus `X3`.
`N38` remains unresolved because X3 failed to produce a final summary across three attempts.
No honest `X1 FAIL / X3 PASS` line has been found yet; the latest inverse attempts were
`N42/N43` binary ties and `N44` X1-over-X3 patch-hygiene separation. Next concrete work is
W25/N45, an N29-derived immutable-test hidden-report-consumer probe.
Bounded `N39` is now a staged systems/toolchain routing result in favor of X1. `X5` remains a live
UI and single-session owner contender after route-healthy `N25` and `N26`, but the newer staged
waves still produced only Gemini route or quota caveats.

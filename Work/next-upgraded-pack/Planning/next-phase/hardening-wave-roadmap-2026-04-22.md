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
| `W18` staged UI/visual/state integration | `READY-TO-RUN` | Does the staged/re-entry split apply to UI implementation when state, ARIA, layout, and raster pixels must stay coherent together? | `E28 / N38` deterministic UI/visual/state integration | `$frontend-engineer` plus `$visualization-engineer` style verifier | read-only sidecar recommended N38; mainline materialized and reference-validated | queued until X3 quota window clears; pre-run gates PASS |
| `W19` staged systems/toolchain recovery re-entry | `READY-TO-RUN` | Does the systems/toolchain `X3 primary` single-shot edge survive staged fresh invocations, recovery source arbitration, runtime-status discipline, ledger, and exact closeout? | `E29 / N39` staged systems/toolchain reentry | `$toolchain-engineer` plus staged re-entry and recovery verifier | mainline materialized from N24 and hardened with N23/N26-style stale-source and owner-continuity traps | queued with N38 until X3 quota window clears; pre-run gates PASS |

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
| W19 next-lane sidecar | inspect N19/N24 and N23/N26 for next staged target | none | next staged gauntlet proposal | `DONE`; N39 materialized locally as staged systems/toolchain recovery candidate while X3 quota is unavailable |

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
| `W18 / E28` | `N38-deterministic-ui-visual-state-integration-gauntlet` | combine N20 UI state, N25 dirty-state/accessibility, and N21 deterministic raster pixels into one staged UI/visual/state integration task | `READY-TO-RUN`; JSON parse, `--bundle-shape-only`, `--expect-start-state`, scratch reference verifier, scope simulation, scorer compile, and `git diff --check` passed |
| `W19 / E29` | `N39-staged-systems-toolchain-reentry-gauntlet` | convert N24 systems/toolchain staging into a four-phase re-entry task with N23/N26-style stale-source recovery, runtime-status discipline, implementation ledger, closeout, exact scope, and functional toolchain oracle | `READY-TO-RUN`; JSON parse, `--bundle-shape-only`, `--expect-start-state`, scratch reference verifier, scope simulation, scorer compile, and `git diff --check` passed |

## Current Admission Decision

`W4 / N24`, `W4 / N25`, and `W6..W17 / N26..N37` are complete. `W18 / N38` and
`W19 / N39` are prepared but not yet scored; they are intentionally held until the X3 quota window
clears so the next X1/X3 batch can run together.

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
22. Materialize `N38-deterministic-ui-visual-state-integration-gauntlet` as W18/E28. `READY-TO-RUN` on 2026-04-23.
23. Materialize `N39-staged-systems-toolchain-reentry-gauntlet` as W19/E29 with recovery source-arbitration hardening. `READY-TO-RUN` on 2026-04-23.
24. After the X3 quota window clears, run `N38,N39` together on `X1` and `X3`, then add `X2`, `X5`, and `X6` only as calibration rows if routes are healthy.

## Current Routing Impact

| Lane | Current Read | Next Need |
|---|---|---|
| long-horizon / cross-role / ownership-budget integration | `X3 primary` for compact integration and incident repair after `N16`, `N27`, `N28`, and `N29` all favor X3 over X1 while binary correctness ties | no more synthetic single-scenario repeat needed; use real-repo lane trial or multi-session delivery simulation if binary separation is required |
| staged delivery / multi-session re-entry | `X1 primary` after `N30`, `N35`, and `N36` produced `X1 PASS` versus `X3 scoreable FAIL` on persisted phase-ledger / re-entry accountability | strong enough for staged-lane routing; next repeat should be a real repo trial, not another synthetic bundle |
| staged review / advisory gate | `X1 primary` after `N37` produced `X1 PASS 98 / 100` versus `X3 scoreable FAIL 35 / 100` on source-bound ADR, exact findings/non-claims, response cues, and closure | strong enough for staged review-gate routing; next repeat should be a real repo review trial or a UX/visual lane where policy remains unresolved |
| systems/toolchain | `X3` primary after `N19` and `N24` both read `95 / 100` versus `X1 86 / 100`; `X2/X5/X6` lower on N24 | no immediate repeat needed unless a new systems subdomain becomes policy-critical |
| systems/toolchain staged recovery re-entry | `N39` is prepared to test whether the N19/N24 `X3` single-shot edge survives staged re-entry plus N23/N26-style stale-source and runtime-status traps | run queued N39 before changing systems/toolchain staged policy |
| UI implementation | `X3` primary versus `X1` after `N20` and `N25`; `X5` is a route-healthy contender after `N25 PASS 98`, but needs another UI-family pass before policy promotion | run queued N38 before changing UI/visual staged policy or X5 promotion |
| scientist/constraints | `X1/X3` correctness tie on `N18`, `N22`, `N31`, `N32`, and `N34`; N31 adds real CEM/MoM evidence, N32 combines MoM with hydrogenic radial Schrodinger, and N34 adds high-load staged performance; `X1` is faster on N34, `X3` is more compact | co-primary; choose X1 for runtime-sensitive scientific solver work and X3 for compact output |
| interface refactor / migration | single-shot `N33` ties and favors X3 compactness; staged `N35` and `N36` split `X1 PASS` versus `X3 scoreable FAIL` | route staged API/interface migrations to X1; keep X3 for compact single-session refactors |
| owner/orchestration | `X3` primary versus `X1` after `N23` and `N26`; `X5` is a route-healthy owner contender after `N26 PASS 100`, but needs another owner-family pass before policy promotion | one more owner-family `X5` check only if deciding between `X3` and `X5`; otherwise move to long-horizon repeat |
| visual/graphics | geometry tied on `S22`; `N21` ties X1/X3 on visual correctness and favors X3 on compactness; Gemini preference not proven | repeat only after Gemini semantic route health is fixed |

## Resume Point

Resume from this roadmap plus:

- `Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md`
- `Work/next-upgraded-pack/Checkpoints/status-2026-04-16.md`
- latest scorer JSON under `Work/next-upgraded-pack/Evidence/`

If interrupted now, resume with the queued `N38,N39` staged batch after the X3 quota window clears.
Systems/toolchain, UI
implementation, owner recovery, compact long-horizon integration, cross-role incident repair, and
ownership-budget repair are confirmed as `X3 primary` versus `X1` by scored lane-fit evidence, while
`N30`, `N35`, and `N36` make `X1 primary` for staged delivery re-entry, staged API/interface migration, and
persisted phase-ledger accountability. `N37` adds the same `X1 primary` read for staged review/advisory
gate work with source-bound ADR, exact finding/non-claim ledgers, response cues, and closure.
`X5` is a live UI and owner-recovery contender after route-healthy `N25` and `N26` wins/ties, but
N27/N28/N29/N30/N32/N33/N34/N35/N36/N37 produced only smoke-gated or route-gated Gemini caveats. The
newest scored read remains: N37 is a scoreable top-pair binary split in favor of X1 for staged review/advisory gates;
N38 and N39 are prepared but not yet scored.

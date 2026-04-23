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
| calibration rows | run `X2` and `X6` when the result may affect lane policy; run `X5` only after a same-session smoke writes output |
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
| `W11` scientific computation hardening | `ADMITTED` | Can a known analytic theoretical-physics solution separate top models when solved numerically under speed/tolerance/convergence gates? | `E21 / N31` analytic-oracle computational physics solver | `$computational-scientist` / `$algorithm-scientist` style verifier | pending; no spawn yet | gate: numerical output must match analytic observables, dimensionless invariants, convergence ratio, and runtime budget without symbolic shortcut |

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
| `W11 / E21` | `N31-scientific-computation-analytic-oracle` | harden generic numerical reasoning with computational theoretical physics: known analytic solution, numerical solver under speed/tolerance/convergence gates | `ADMITTED`; materialization next |

## Current Admission Decision

`W4 / N24`, `W4 / N25`, `W6 / N26`, `W7 / N27`, `W8 / N28`, `W9 / N29`, and `W10 / N30` are complete.

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

Next admitted branch: add a scientific computation hardening wave to the generic numerical reasoning
lane. The user explicitly requested a difficult computational theoretical physics task with a known
analytic solution, solved numerically and quickly, so the result can separate actual numerical
competence from prose.

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
15. Materialize `N31-scientific-computation-analytic-oracle` as W11/E21.

## Current Routing Impact

| Lane | Current Read | Next Need |
|---|---|---|
| long-horizon / cross-role / ownership-budget integration | `X3 primary` for compact integration and incident repair after `N16`, `N27`, `N28`, and `N29` all favor X3 over X1 while binary correctness ties | no more synthetic single-scenario repeat needed; use real-repo lane trial or multi-session delivery simulation if binary separation is required |
| staged delivery / multi-session re-entry | `X1 primary` after `N30` produced `X1 PASS` versus `X3 scoreable FAIL` on persisted phase-ledger completeness | repeat only if this becomes a hard global default; otherwise use as routing evidence |
| systems/toolchain | `X3` primary after `N19` and `N24` both read `95 / 100` versus `X1 86 / 100`; `X2/X5/X6` lower on N24 | no immediate repeat needed unless a new systems subdomain becomes policy-critical |
| UI implementation | `X3` primary versus `X1` after `N20` and `N25`; `X5` is a route-healthy contender after `N25 PASS 98`, but needs another UI-family pass before policy promotion | one more UI-family `X5` check only if deciding between `X3` and `X5` |
| scientist/constraints | `X1/X3` correctness tie on `N18`; `N22` also ties by binary, with `X1 100`, `X3 99`, and `X3` far more compact | W11 admitted: computational theoretical physics analytic-oracle numerical solver |
| owner/orchestration | `X3` primary versus `X1` after `N23` and `N26`; `X5` is a route-healthy owner contender after `N26 PASS 100`, but needs another owner-family pass before policy promotion | one more owner-family `X5` check only if deciding between `X3` and `X5`; otherwise move to long-horizon repeat |
| visual/graphics | geometry tied on `S22`; `N21` ties X1/X3 on visual correctness and favors X3 on compactness; Gemini preference not proven | repeat only after Gemini semantic route health is fixed |

## Resume Point

Resume from this roadmap plus:

- `Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md`
- `Work/next-upgraded-pack/Checkpoints/status-2026-04-16.md`
- latest scorer JSON under `Work/next-upgraded-pack/Evidence/`

If interrupted now, resume after the `W10 / N30` closeout commit. Systems/toolchain, UI
implementation, owner recovery, compact long-horizon integration, cross-role incident repair, and
ownership-budget repair are confirmed as `X3 primary` versus `X1` by scored lane-fit evidence, while
`N30` makes `X1 primary` for staged delivery re-entry and persisted phase-ledger accountability.
`X5` is a live UI and owner-recovery contender after route-healthy `N25` and `N26` wins/ties, but
N27/N28/N29/N30 produced only smoke-gated `REQUEUE`. The next useful work item is `W11 / N31`:
scientific computation hardening with a known analytic physics oracle and fast numerical solve.

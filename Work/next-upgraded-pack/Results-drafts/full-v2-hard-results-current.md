Date: 2026-04-26
Owner: `$lead`
Status: `ACTIVE`

## Purpose

`full-v2-hard` is the current canonical hardened replacement for the old full-v2 leaderboard.
For model ranking and routing, legacy full-v2 is now `DEPRECATED / SUPERSEDED`.

The old `S01..S33 + N01..N07` `/40` table and the earlier `S01..S33` table are retained only
as historical pre-v3 ceiling-effect baselines. They are not used for current classification because
they scored weak contracts and produced near-ceiling rows such as `40 / 40` and `39 / 40`.

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
| `X2` | `gpt-spark` | `12 / 40` | `12 PASS`, `28 FAIL`, `0 NOT-RUN` | closed lower-bound row after 2026-04-26 fill run |
| `X6` | `gemini3.1flash-lite-preview` | `13 / 40` | `13 PASS`, `19 FAIL`, `8 NOT-RUN` | partial lower-bound row; remaining slots are timeout/auth-route `NOT-RUN` after 2026-04-26 closure retry |
| `X4` | Claude China route, `opus --effort max` | `32 / 40` | `32 PASS`, `8 FAIL`, `0 NOT-RUN` | admitted final closing comparison; weaker on staged/interface/review and UI dirty-state gates |

Interpretation: the current hardened `/40` is a global tie for `X1` and `X3`, but not a role tie.
`X4` is close enough to be useful as a Claude-line comparator, but it is not tied with the top pair.
The failure classes are different:

| Row | Scoreable fails inside the 40-slot surface | Failure class |
|---|---|---|
| `X1` | `N47`, `N48`, `N56`, `N57`, `N58` | preserved hidden semantics/physics/scope, but exceeded visible operator-output budget |
| `X3` | `N35`, `N36`, `N37`, `N39`, `N40` | missed staged re-entry, migration ledger, source binding, owner continuity, or closure semantics |
| `X4` | `N25`, `N35`, `N36`, `N37`, `N39`, `N40`, `N43`, `N57` | similar staged/interface/review misses plus UI dirty-state failures; `N60` completed PASS in the original batch |

## Line Summary

| Line                                  | Slots             |   `X1` |   `X3` |   `X4` | Read     |
|---------------------------------------|-------------------|-------:|-------:|-------:|----------|
| `L00 owner/control`                   | `N17,N26,N40,N56` | `3/4`  | `3/4`  | `3/4`  | split    |
| `L01 advisory.repo-understanding`     | `S03,S04,S06`     | `3/3`  | `3/3`  | `3/3`  | near-tie |
| `L02 advisory.design-adr`             | `S05,S07,S09`     | `3/3`  | `3/3`  | `3/3`  | near-tie |
| `L03 design.ui-ux-structure`          | `S08,N01,N02`     | `3/3`  | `3/3`  | `3/3`  | near-tie |
| `L04 worker.reasoning-constraints`    | `N22,N32,N58`     | `2/3`  | `3/3`  | `3/3`  | split    |
| `L05 worker.default-implementation`   | `N35,N36,N57`     | `2/3`  | `1/3`  | `0/3`  | split    |
| `L06 systems/performance-worker`      | `N19,N39,N59`     | `3/3`  | `2/3`  | `2/3`  | split    |
| `L07 worker.ui-implementation`        | `N25,N47,N60`     | `2/3`  | `3/3`  | `2/3`  | `X3`     |
| `L08 worker.visual/graphics`          | `S22,N21,N48`     | `2/3`  | `3/3`  | `3/3`  | `X3`     |
| `L09 review.pre-pr`                   | `S25,N03,N04`     | `3/3`  | `3/3`  | `3/3`  | near-tie |
| `L10 review.security`                 | `S27,N05,N06`     | `3/3`  | `3/3`  | `3/3`  | near-tie |
| `L11 review.performance-architecture` | `S28,N07,N37`     | `3/3`  | `2/3`  | `2/3`  | `X1`     |
| `L12 review.ui-visual-correctness`    | `S29,S30,N43`     | `3/3`  | `3/3`  | `2/3`  | near-tie |

## Priority Matrix

Priority is routing priority, not abstract model quality. `P0` changes provider choice today,
`P1` is a useful preference with close verification, and `P2` is a near-tie or low-yield lane.

| Line                                  | Pri  | Order       | Trigger                      | Follow-up            |
|---------------------------------------|------|-------------|------------------------------|----------------------|
| `L00 owner/control`                   | `P0` | `X3 > X1`   | compact owner packet         | rerun `X5` later     |
|                                       |      | `X1 > X3`   | staged owner/re-entry        |                      |
| `L01 advisory.repo-understanding`     | `P2` | `X1 = X3`   | repo facts / source inspect  | stop hardening now   |
|                                       |      | `X5` viable | route healthy only           |                      |
| `L02 advisory.design-adr`             | `P1` | `X1 = X3`   | single-shot ADR              | use `L11` if staged  |
| `L03 design.ui-ux-structure`          | `P2` | `X1 = X3`   | static UX / state-flow       | low yield            |
| `L04 worker.reasoning-constraints`    | `P1` | `X1 = X3`   | science correctness          |                      |
|                                       |      | `X3 > X1`   | compact science/runtime      | speed split open     |
| `L05 worker.default-implementation`   | `P0` | `X1 > X3`   | staged API/interface         |                      |
|                                       |      | `X3 > X1`   | compact single-shot          |                      |
| `L06 systems/performance-worker`      | `P0` | `X1 > X3`   | staged systems recovery      |                      |
|                                       |      | `X3 > X1`   | compact perf hot path        | verify turnaround    |
| `L07 worker.ui-implementation`        | `P0` | `X3 > X1`   | compact UI state/render      | staged X3 gap        |
| `L08 worker.visual/graphics`          | `P0` | `X3 > X1`   | compact raster/visual patch  | N48/N60 evidence     |
|                                       | `P1` | `X1` scored | pure image localization      | N61 diagnostic only; no binary winner |
| `L09 review.pre-pr`                   | `P2` | `X1 = X3`   | tuple-exact review           | staged uses `L11`    |
| `L10 review.security`                 | `P2` | `X1 = X3`   | tuple-exact security         | stop hardening now   |
| `L11 review.performance-architecture` | `P0` | `X1 > X3`   | staged source-bound review   | strongest review sep |
| `L12 review.ui-visual-correctness`    | `P2` | `X1 = X3`   | UI/visual review             | low yield            |

## Visual Pixel-Localization Diagnostic

`N61-visual-pixel-localization-gauntlet` materializes the earlier external pixel-localization
side evidence as diagnostic `E51`: one `2200 x 1600` raster, six `13 x 13` solid targets, same-color
decoys, and point-distance scoring with a several-pixel pass window. It is not part of the `full-v2-hard`
`/40` denominator because it has not replaced a routed L08 slot.

The first raw runs exposed a prompt/schema defect: the old array contract permitted candidate-list
answers with duplicate ids. N61 now requires `points` to be an object keyed by target id, and the
verifier reports best-duplicate diagnostics for legacy array outputs. The current table uses the
post-fix object-map rerun and a softer secondary score; binary `PASS` remains strict.

| Row | Model/profile | Route class | Verdict | Score | Strict mean / max px | Coverage | Notes |
|---|---|---|---|---:|---:|---|---|
| `X1` | `gpt-5.5` | scoreable | `FAIL` | `65.1` | `77.065 / 106.231` | `6 / 6`; no within-window targets | object-map output fixed; all points wrong-but-bounded |
| `X3` | `opus 4.7max` | scoreable | `FAIL` | `50.0` | `344.406 / 1981.709` | `6 / 6`; three within-window targets | `cyan` selected a decoy region |
| `X5` | `gemini3.1pro` | runtime | `NOT-RUN` | n/a | n/a | n/a | `600s` timeout before JSON output |
| `X6` | `gemini3.1flash-lite-preview` | scoreable | `FAIL` | `40.0` | `363.604 / 1973.736` | `6 / 6`; no within-window targets | route/quota live; `cyan` selected a decoy region |

Fallback diagnostic `gemini-3-flash-preview` was also attempted and timed out after `240s` before
JSON output. It is route evidence only, not an official `X5` score.

Current visual split:

| Visual task type | Priority read |
|---|---|
| compact visual/raster code patch | `X3` first under N48/N60 benchmark evidence |
| staged UI/visual-state delivery | `X1` has the staged scoreable evidence; single-session N60 favors `X3` by cost |
| pure image localization / tiny object pick | no binary winner; post-fix N61 gives `X1` a scored edge over `X3` and `X6`, while X5 is route-unhealthy |
| calibrated actual screenshot grounding | `X1` after N80; N68's earlier X3 edge is superseded for calibrated screenshot work |

## Frame-Inversion W41 Diagnostic

`N62` and `N63` test whether the current `X1`/`X3` split is just prompt-frame wording. They are not
part of the `full-v2-hard` `/40` denominator.

| Scenario | Frame inversion | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|---|
| `N62` | compact prompt over N35-class staged interface requirements | `PASS` | `PASS` | X3 can perform the migration in a compact single-pass frame; N35/N36 are staged re-entry/accountability evidence, not generic migration evidence |
| `N63` | staged prompt over N57-class compact API migration plus operator budget | `FAIL`; budget `545831 > 40000`, hidden API/scope `PASS` | `PASS`; `3190 <= 40000` | X1's low-noise/operator-budget failure persists under staged wording; X3 remains primary for compact operator-budget migration |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N62` | `FAIL`; missing `candidate/workspace/src/interfaceflow/api.py` in exact scope | `NOT-RUN`; shell timeout before `worker-output.txt` / `summary.json` | not run on scenario |
| `N63` | `FAIL`; budget `125688 > 40000`, hidden API/scope `PASS` | `NOT-RUN`; shell timeout before `worker-output.txt` / `summary.json` | quota probe timed out after `180s` with no output file and no explicit quota/reset message |

W41 interpretation: keep execution-shape routing. Use X1 for staged re-entry, multi-session
accountability, and phase-ledger closure. Use X3 for compact low-noise/operator-budget implementation.

## Security Depth W42 Diagnostic

`N64-security-depth-review-gauntlet` probes unresolved `L10 review.security` with nine exact
vulnerability tuples and explicit false-positive traps. It is not part of the `full-v2-hard` `/40`
denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N64` | `PASS`; nine exact findings, wrapper `0` | `PASS`; nine exact findings, wrapper `0` | `binary tie remains`; ordinary security-depth review stays `X1 / X3 near-tie` |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N64` | `FAIL`; did not edit the starter report | local verifier `PASS`, but wrapper `1` after Gemini capacity/tool-loop/AbortError, so runtime-caveat `NOT-RUN` | not run; latest Pro quota probe timed out without output |

W42 interpretation: do not assign a semantic security primary from N64. X3 is much more compact
(`1663` bytes versus X1 `131863`), but both top rows meet the security oracle. Keep `L10` near-tie
unless a later security task produces objective semantic misses.

## Visual Correctness W43 Diagnostic

`N65-visual-correctness-review-gauntlet` probes unresolved `L12 review.ui-visual-correctness` with
eight exact UI visual defect tuples over DOM/CSS/state/screenshot-probe evidence. It is not part of
the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N65` | `PASS`; eight exact findings, wrapper `0` | `PASS`; eight exact findings, wrapper `0` | `binary tie remains`; ordinary visual-correctness review stays `X1 / X3 near-tie` |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N65` | `FAIL`; did not edit the starter report | `NOT-RUN`; shell timeout after `1800s`, no `worker-output.txt` or `summary.json` | not run; latest Pro quota probe timed out without output |

W43 interpretation: do not assign a semantic visual-review primary from N65. X3 is much more
compact (`1666` bytes versus X1 `94940`), but both top rows meet the visual correctness oracle.
Keep `L12` near-tie for ordinary review; keep X3 primary for compact visual/raster implementation
and keep N61 pure-pixel localization as a separate diagnostic.

## Conflicting Evidence W44 Diagnostic

`N66-conflicting-evidence-fact-memo-gauntlet` probes `L01 advisory.repo-understanding` with current
code/tests, accepted ADR, stale README, draft ADR, and stale migration-status evidence. It is not
part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N66` | `PASS`; exact source ranking and conflict ledger, wrapper `0` | `PASS`; exact source ranking and conflict ledger, wrapper `0` | `binary tie remains`; repo-understanding stays `X1 / X3 near-tie` |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N66` | `FAIL`; misses source-ranking/conflict/fact/non-claim gates | `FAIL`; misses source-ranking/conflict/fact/non-claim gates | not run; latest Pro quota probe timed out without output |

W44 interpretation: do not assign a semantic repo-understanding primary from N66. X3 is much more
compact (`1725` bytes versus X1 `169439`), but both top rows meet the source-authority oracle.
N66 is useful lower-bound evidence because both X2 and X6 fail scoreably.

## Cross-Phase Integration W45 Diagnostic

`N67-cross-phase-integration-owner-gauntlet` probes staged integration-owner behavior across four
fresh invocations. It is not part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N67` | `PASS`; detects backend/frontend/QA cursor mismatch before QA, wrapper `0` | `FAIL`; compact but misses QA-stop, repair/re-entry, and closure markers, wrapper `0` | staged cross-phase integration-owner work is `X1 primary` |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N67` | `FAIL`; exact changed-path contract failed because `candidate/integration-ledger.json` was not changed | runtime-caveat `NOT-RUN`; wrapper `1` plus verifier failures | not run; latest Pro quota probe timed out without output |

W45 interpretation: promote the existing staged-governance routing rule for integration-owner work.
Use X1 for cross-phase compatibility, QA-stop, repair/re-entry, and closure packets. Do not fold N67
into the `/40` score until there is a documented slot-replacement decision.

## Actual Screenshot Visual Review W46 Diagnostic

`N68-actual-screenshot-visual-review-gauntlet` probes screenshot-first visual grounding with one
actual PNG, eight seeded defects, coordinate windows, and false-positive traps. It is not part of the
`full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N68` | `FAIL`; `70 / 100`; missed search-input, timeline grounding, and non-finding ledger | `FAIL`; `80 / 100`; missed search-input and risk-score coordinate grounding | no binary winner; actual screenshot grounding gives X3 a scored edge |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N68` | `NOT-RUN`; current visual runner has no X2 vision route | `FAIL`; `20 / 100`; coordinates scaled/misaligned | not run; Pro smoke timed out after `264s` with no output |

W46 interpretation: do not assign a binary visual-review primary from N68 alone. N68 remains
historical loose screenshot-review context, not the current calibrated screenshot-grounding read.

## Calibrated Screenshot Grounding W58 Diagnostic

`N80-screenshot-grounding-review-v2` repeats actual screenshot grounding with deterministic image
generation, ten semantic visual-defect tuples, a nonzero `22 px` coordinate window, false-positive
traps, and a threshold scorer. It is not part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N80` | `PASS`; `82 / 100`; `8 / 10`; mean/max `2.855 / 7.071 px` | `FAIL`; `63 / 100`; `7 / 10`; mean/max `8.067 / 17.117 px`; one false-positive header ornament | scoreable X1-over-X3 calibrated screenshot-grounding separator |

W58 interpretation: actual screenshot grounding is `X1 primary` when calibrated pixel windows,
semantic defect tuples, and false-positive traps are hard verifier requirements. Keep N65 as ordinary
visual-review near-tie and keep N61 as pure pixel-localization diagnostic.

## Evidence-Conflict Action-Plan W59 Diagnostic

`N81-evidence-conflict-repo-action-plan` repeats repo-understanding with command output and a bounded
action-plan contract instead of a fact memo only. It is not part of the `full-v2-hard` `/40`
denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N81` | `PASS`; `100 / 100`; `24 / 24`; wrapper `0` | `PASS`; `100 / 100`; `24 / 24`; wrapper `0` | `binary tie remains`; advisory repo-understanding/action-plan stays near-tie |

W59 interpretation: a stricter single-shot evidence-conflict action plan still does not split the
top pair. Future advisory hardening should use staged source arbitration or decision-context checks;
literal forbidden-snippet traps are too gameable.

## UX Runtime State W60 Diagnostic

`N82-ux-structure-runtime-state-spec` converts UX structure into a valid JSON state-spec with
runtime states, breakpoint invariants, affordance rules, copy ledger, handoff contracts, and
non-goals. It is not part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N82` | `PASS`; `100 / 100`; `27 / 27`; wrapper `0` | `PASS`; `100 / 100`; `27 / 27`; wrapper `0` | `binary tie remains`; UX structure/runtime-state stays near-tie |

W60 interpretation: single-shot objective UX JSON does not split the top pair. Future UX separators
need behavioral runtime simulation, staged UX review, or visual-grounded oracles.

## Interface Refactor Breakage W61 Diagnostic

`N83-interface-refactor-breakage-hunt` retests interface-refactor quality through behavioral hidden
consumers rather than output budget. It requires a batch API hidden consumer, shared duplicate state,
structured report inputs, legacy method removal, exact ten-path scope, visible regression markers,
and a migration ledger. It is not part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N83` | `PASS`; wrapper `0`; hidden batch consumer and structured-report gates pass | `PASS`; wrapper `0`; same runtime and artifact gates pass | `binary tie remains`; ordinary hidden-consumer interface refactor stays near-tie |

W61 interpretation: N83 confirms that behavioral single-session interface-refactor checks alone do
not split the top pair. Use X1 for staged interface/API migration after N35/N36, use X3 for compact
operator-budget API migration after N57, and keep ordinary hidden-consumer refactor as near-tie.
The v2 runner now classifies top-level `.pytest_cache/` as auxiliary generated cache.

## Security Review Reproduction W62 Diagnostic

`N84-security-review-repro-gauntlet` retests ordinary security review after N64 with JSON exploit
reproduction binding instead of a markdown finding table. It requires exact finding tuples,
`R1..R9` reproduction case binding, source evidence, violated invariant, fix-boundary ownership,
`B1..B3` false-positive suppression, exact `REVISE` gate decision, and exact one-file report scope.
It is not part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N84` | `PASS`; wrapper `0`; exact JSON repro report gates pass | `PASS`; wrapper `0`; same exact JSON report gates pass | `binary tie remains`; ordinary single-session security review stays near-tie |

W62 interpretation: exploit reproduction binding and false-positive suppression improve ordinary
security-review scoreability, but they still do not split the top pair. Use X1 for staged security
re-entry after N78; use compactness only as a secondary preference for ordinary single-session
security review.

## Real-Repo Patch Quality W47 Diagnostic

`N69-realrepo-patch-quality-scorecard` probes a compact implementation patch with hidden ledger
semantics, runtime budget, exact required paths, auxiliary churn, and output-cost scoring. It is not
part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N69` | `PASS`; `85 / 100`; hidden semantics pass; exact two-file patch; output bytes `149015` | `PASS`; `90 / 100`; hidden semantics pass; output bytes `2037`; auxiliary cache churn | `binary tie remains`; X3 wins cost score, X1 wins patch-hygiene score |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N69` | `FAIL`; `35 / 100`; no patch, hidden semantics and ledger failed | `FAIL`; `35 / 100`; order-independence semantics and ledger failed | smoke timed out after `244s` with no output and no explicit quota/reset |

W47 interpretation: use N69 as scored patch-quality/cost evidence, not as a binary primary. X3 is
better when low output/cost dominates and generated-cache churn is controlled. X1 is cleaner on exact
patch hygiene because it changed only the two required files.

## Entitlement Event Migration W48 Diagnostic

`N70-entitlement-event-migration-scorecard` repeats the W47 patch-quality axis on a multi-file
schema migration with hidden consumers. It is not part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N70` | `PASS`; `85 / 100`; hidden schema-v2 migration semantics pass; exact four-file patch; output bytes `229032` | `PASS`; `90 / 100`; hidden schema-v2 migration semantics pass; output bytes `2395`; auxiliary cache churn | `binary tie remains`; X3 wins cost score, X1 wins patch-hygiene score |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N70` | `FAIL`; `15 / 100`; no patch, parser exception and ledger failed | runtime-caveat `NOT-RUN`; wrapper `1` after Gemini capacity/tool-loop noise | not run semantically; latest Pro smoke timed out after `244s` with no output |

W48 interpretation: multi-file hidden-consumer migration still ties X1/X3 by binary. X3 remains the
compact/cost winner; X1 remains the clean-workspace patch-hygiene winner. This reduces the value of
adding more synthetic schema-migration variants unless a new semantic axis is introduced.

## Test-Led Regression W49 Diagnostic

`N71-test-led-rate-limit-regression-scorecard` probes required regression-test delivery plus hidden
behavior. It is not part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N71` | `PASS`; `83 / 100`; behavior and regression test pass; output bytes `135535`; auxiliary cache churn | `PASS`; `90 / 100`; behavior and regression test pass; output bytes `2410`; auxiliary cache churn | `binary tie remains`; X3 wins cost score |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N71` | `FAIL`; `15 / 100`; no patch, behavior/test/ledger failed | `FAIL`; `15 / 100`; visible tests, regression-test artifact, and ledger failed | not run; current Pro route/runtime remains unhealthy |

W49 interpretation: this test-led implementation construction is negative X1-primary evidence. Both
top rows can satisfy the required regression test and hidden behavior; X3 remains the lower-cost row.

## Caller-Spanning Refactor W50 Diagnostic

`N72-caller-spanning-api-refactor-scorecard` probes interface breakage across API, service, CLI, and
report callers. It is not part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N72` | `PASS`; `83 / 100`; hidden API/service/CLI/report callers pass; output bytes `146983`; auxiliary cache churn | `PASS`; `90 / 100`; hidden API/service/CLI/report callers pass; output bytes `2599`; auxiliary cache churn | `binary tie remains`; X3 wins cost score |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N72` | `FAIL`; `15 / 100`; no patch, hidden caller contracts and ledger failed | `NOT-RUN`; shell timeout after `1800s`, no `summary.json`; local partial-run probe also failed | not run; smoke timed out after `244s` with no output and no explicit quota/reset |

W50 interpretation: caller-spanning hidden tests still tie X1/X3 by binary in a compact
single-session frame. Keep staged API/interface migration as X1-primary after N35/N36, but treat
ordinary single-session caller refactors as binary near-tie with X3 cost advantage and an explicit
cache/scope hygiene guard.

## DOM Event Runtime UI W51 Diagnostic

`N73-dom-event-runtime-ui-scorecard` probes runtime UI behavior through a deterministic Node
DOM/event harness. It is not part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N73` | `PASS`; `93 / 100`; DOM filter, keyboard dirty, save, scope, and ledger pass; output bytes `138818` | `PASS`; `93 / 100`; DOM filter, keyboard dirty, save, scope, and ledger pass; output bytes `2467`; elapsed cost bucket partial | `binary tie remains`; no runtime-UI correctness winner |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N73` | `FAIL`; `15 / 100`; no patch, filter/keyboard/save/ledger failed | `FAIL`; `15 / 100`; dirty status and ledger completeness failed; only three required paths changed | not run; latest Pro smoke timed out after `244s` with no output |

W51 interpretation: actual DOM/event runtime checks did not separate X1/X3 by binary. Keep compact
UI implementation X3-leaning only when low-noise/output budget is a hard gate; runtime UI correctness
without that budget remains X1/X3 near-tie.

## DOM Runtime Output Budget W52 Diagnostic

`N74-dom-runtime-output-budget-scorecard` repeats the N73 DOM/event runtime harness and adds a
visible `50000` byte operator-output budget. It is not part of the `full-v2-hard` `/40`
denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N74` | `FAIL`; `80 / 100`; DOM runtime, exact five-path scope, and ledger pass; output bytes `241980` fails budget | `PASS`; `100 / 100`; DOM runtime, exact scope, ledger, and budget pass; output bytes `2085` | compact inverse separator; X3 primary when runtime UI has a hard output budget |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N74` | not run in W52; W51 just calibrated the same DOM runtime base | not run in W52; W51 just calibrated the same DOM runtime base | not run; latest Pro smoke timed out after `244s` with no output |

W52 interpretation: N73 and N74 split the UI-runtime rule cleanly. Without a strict visible output
budget, X1 and X3 tie on runtime UI correctness. With the output budget promoted to a hard verifier,
X1 fails only budget while X3 passes all gates.

## Persisted-State Replay Migration W53 Diagnostic

`N75-persisted-state-replay-migration-scorecard` probes stateful migration, replay idempotency,
checkpoint rollback, schema-v2 persistence envelopes, exact scope, and migration-ledger coverage. It
is not part of the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N75` | `PASS`; `83 / 100`; migration, replay, rollback, persist/load, exact scope, and visible regression pass; output bytes `148703`; auxiliary cache churn | `PASS`; `83 / 100`; same semantic gates pass; output bytes `2577`; auxiliary cache churn and elapsed cost bucket partial | `binary tie remains`; ordinary single-session persisted-state migration is not a top-pair separator |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N75` | `PASS`; `75 / 100`; semantic gates pass, but output cost zero and auxiliary session-log churn | `NOT-RUN`; shell timeout after `1800s`, no `summary.json` | not run; latest Pro smoke timed out after `244s` with no output |

W53 interpretation: this fixture shape is too easy as a semantic separator. X1, X3, and X2 all pass
the hidden persisted-state migration oracle. Further work on this lane should use staged re-entry,
real repo integration, or stricter operability/runtime constraints rather than more hidden replay
cases in the same single-session frame.

## Staged Persisted-State Reentry W54 Diagnostic

`N76-staged-persisted-state-reentry-gauntlet` repeats the N75 runtime oracle in a staged re-entry
shape: source ledger, migration implementation, re-entry validation, and closeout. It is not part of
the `full-v2-hard` `/40` denominator.

| Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Read |
|---|---|---|---|
| `N76` | `PASS`; `85 / 100`; staged source, migration, re-entry, closeout, and runtime gates pass; output bytes `870319` | `FAIL`; `15 / 100`; missing `migrator.py` scope, schema version, persist envelope, and ledger/reentry/closeout contracts | X1 staged persisted-state separator |

Calibration rows:

| Scenario | `X2 / gpt-spark` | `X6 / flash-lite` | `X5 / gemini3.1pro` |
|---|---|---|---|
| `N76` | `FAIL`; `70 / 100`; semantic behavior mostly passes but exact staged scope fails | `NOT-RUN`; timeout during phase 2 after Gemini capacity/registry errors, no final `summary.json` | not run; latest Pro smoke timed out after `244s` with no output |

W54 interpretation: persisted-state migration now follows the same execution-shape split as API,
owner, systems, and incident lanes. Single-session replay migration is near-tie after N75; staged
re-entry with source accountability and closeout is X1-primary after N76.

## W55 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W55` | `N77 security capability runtime patch` | `PASS`; `85 / 100`; hidden exploit oracle, exact scope, regression test, and ledger pass; output-cost score `0` | `PASS`; `93 / 100`; same security gates pass; low output cost; auxiliary cache churn lowers artifact score | `X2 FAIL 15`; `X6 NOT-RUN` no-summary timeout | `binary tie remains`; X3 has scored cost edge, no semantic security primary |

Decision: W55 proves that a single-session security implementation patch with runtime exploit tests
is still not enough to split the top pair by binary correctness. It does separate lower rows: X2 is
a scoreable no-op fail and X6 remains a runtime caveat. Keep ordinary security implementation as
`X1 / X3` near-tie; if this lane needs a primary, build a staged security re-entry variant rather
than adding more exploit cases to N77.

## W56 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W56` | `N78 staged security re-entry` | `PASS`; `85 / 100`; runtime exploit oracle, threat ledger, implementation, validation, re-entry, closeout, and phase paths pass | scoreable `FAIL`; `23 / 100`; percent-encoded CRLF redirect trap plus staged ledger/validation/closeout contract gaps | `X2 FAIL 45`; `X6 NOT-RUN` no-summary timeout | X1 primary for staged security re-entry |

Decision: W56 converts the W55 single-session tie into a staged separator. Use X1 for staged
security re-entry packets where threat ledger, exploit validation, re-entry state, closeout, and
runtime security semantics are all part of the artifact. Keep compact single-session security patch
work as near-tie after W55.

## Slot Matrix

Legend: `P` = scoreable pass, `F` = scoreable fail, `NR` = not-run/runtime-route/no-summary on this hardened slot.

| # | Line | Slot | X1 | X3 | X4 | X2 | X5 | X6 | Source |
|---:|---|---|---|---|---|---|---|---|---|
| `01` | `L00` | `N17 owner orchestration` | `P` | `P` | `P` | `P` | `NR` | `P` | `n17-owner-routing-rubric` |
| `02` | `L00` | `N26 owner recovery repeat` | `P` | `P` | `P` | `F` | `P` | `F` | `n26-owner-wave-rubric` |
| `03` | `L00` | `N40 staged owner recovery` | `P` | `F` | `F` | `F` | `NR` | `F` | `n40-staged-owner-rubric` |
| `04` | `L00` | `N56 compact owner operator-budget` | `F` | `P` | `P` | `F` | `NR` | `NR` | `n56-owner-operator-budget-rubric` |
| `05` | `L01` | `S03 repo/advisory` | `P` | `P` | `P` | `P` | `P` | `F` | `v2-core12-tie-hardened`; X2/X6 fill |
| `06` | `L01` | `S04 knowledge/archive` | `P` | `P` | `P` | `F` | `P` | `P` | `v2-core12-tie-hardened`; X2/X6 fill |
| `07` | `L01` | `S06 source investigation` | `P` | `P` | `P` | `F` | `P` | `F` | `v2-core12-tie-hardened`; X2/X6 fill |
| `08` | `L02` | `S05 product/design ADR` | `P` | `P` | `P` | `P` | `P` | `P` | `v2-core12-tie-hardened`; X2/X6 fill |
| `09` | `L02` | `S07 architecture ADR` | `P` | `P` | `P` | `F` | `P` | `P` | `v2-core12-tie-hardened`; X2/X6 fill |
| `10` | `L02` | `S09 planning ADR` | `P` | `P` | `P` | `F` | `P` | `P` | `v2-core12-tie-hardened`; X2/X6 fill |
| `11` | `L03` | `S08 UI/UX structure` | `P` | `P` | `P` | `P` | `P` | `P` | `v2-core12-tie-hardened`; X2/X6 fill |
| `12` | `L03` | `N01 visual hierarchy` | `P` | `P` | `P` | `P` | `P` | `P` | `v2-core12-tie-hardened`; X2/X6 fill |
| `13` | `L03` | `N02 state flow trace` | `P` | `P` | `P` | `F` | `P` | `F` | `v2-core12-tie-hardened`; E2 calibration |
| `14` | `L04` | `N22 numerical stability` | `P` | `P` | `P` | `F` | `NR` | `P` | `n22-numerical-stability-rubric`; X6 fill |
| `15` | `L04` | `N32 dual physics oracle` | `P` | `P` | `P` | `F` | `NR` | `F` | `n32-dual-physics-rubric`; X6 fill |
| `16` | `L04` | `N58 MoM batch runtime` | `F` | `P` | `P` | `F` | `NR` | `F` | `n58-mom-batch-runtime-rubric`; X6 fill |
| `17` | `L05` | `N35 staged interface migration` | `P` | `F` | `F` | `P` | `NR` | `NR` | `n35-staged-interface-rubric` |
| `18` | `L05` | `N36 staged API migration` | `P` | `F` | `F` | `F` | `NR` | `NR` | `n36-staged-api-rubric` |
| `19` | `L05` | `N57 compact API migration` | `F` | `P` | `F` | `F` | `NR` | `NR` | `n57-compact-api-migration-rubric` |
| `20` | `L06` | `N19 systems/toolchain` | `P` | `P` | `P` | `P` | `NR` | `F` | `n19-systems-toolchain-rubric` |
| `21` | `L06` | `N39 staged systems recovery` | `P` | `F` | `F` | `F` | `NR` | `F` | `n39-staged-toolchain-rubric` |
| `22` | `L06` | `N59 real-repo performance cache` | `P` | `P` | `P` | `F` | `NR` | `F` | `n59-perf-cache-rubric`; X6 fill |
| `23` | `L07` | `N25 UI dirty-state repeat` | `P` | `P` | `F` | `F` | `P` | `F` | `n25-ui-dirty-repeat-rubric`; X6 fill |
| `24` | `L07` | `N47 UI operator-budget` | `F` | `P` | `P` | `F` | `NR` | `F` | `n47-ui-operator-budget-rubric`; X2/X6 fill |
| `25` | `L07` | `N60 UI visual-state reentry` | `P` | `P` | `P` | `F` | `NR` | `F` | `n60-ui-reentry-rubric`; X6 fill |
| `26` | `L08` | `S22 adversarial geometry` | `P` | `P` | `P` | `F` | `NR` | `P` | `x1-mainline-hardening-no-new-failures`; X2/X6 fill |
| `27` | `L08` | `N21 visual raster` | `P` | `P` | `P` | `P` | `NR` | `F` | `n21-visual-raster-rubric`; X6 fill |
| `28` | `L08` | `N48 visual raster operator-budget` | `F` | `P` | `P` | `F` | `NR` | `F` | `n48-visual-operator-budget-rubric`; X2/X6 fill |
| `29` | `L09` | `S25 pre-pr review` | `P` | `P` | `P` | `F` | `F` | `F` | `v2-core12-tie-hardened`; X2/X6 fill |
| `30` | `L09` | `N03 generic review findings` | `P` | `P` | `P` | `F` | `F` | `F` | `v2-core12-tie-hardened`; X2/X6 fill |
| `31` | `L09` | `N04 regression triage` | `P` | `P` | `P` | `F` | `P` | `NR` | `v2-core12-tie-hardened`; X2 fill; X6 timeout |
| `32` | `L10` | `S27 security review` | `P` | `P` | `P` | `F` | `P` | `NR` | `v2-core12-tie-hardened`; X2 fill; X6 timeout |
| `33` | `L10` | `N05 secret exposure review` | `P` | `P` | `P` | `P` | `F` | `P` | `v2-core12-tie-hardened`; X2/X6 fill |
| `34` | `L10` | `N06 authz trust boundary` | `P` | `P` | `P` | `F` | `P` | `P` | `v2-core12-tie-hardened`; X2/X6 fill |
| `35` | `L11` | `S28 performance review` | `P` | `P` | `P` | `P` | `NR` | `P` | wave-2 tuple-exact hardening; X2/X6 fill |
| `36` | `L11` | `N07 scalability/architecture review` | `P` | `P` | `P` | `F` | `NR` | `P` | wave-2 tuple-exact hardening; X2/X6 fill |
| `37` | `L11` | `N37 staged adversarial review gate` | `P` | `F` | `F` | `P` | `NR` | `NR` | `n37-staged-review-rubric` |
| `38` | `L12` | `S29 accessibility/UI review` | `P` | `P` | `P` | `P` | `NR` | `NR` | wave-2 tuple-exact hardening; X2 fill; X6 timeout |
| `39` | `L12` | `S30 UX interaction review` | `P` | `P` | `P` | `F` | `NR` | `F` | E2 hardened separator slice |
| `40` | `L12` | `N43 UI immutable-test hotfix` | `P` | `P` | `F` | `F` | `NR` | `F` | `x1-mainline-hardening-no-new-failures`; X2/X6 fill |

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
| staged delivery/re-entry, staged API/interface migration, staged systems recovery, staged owner recovery, staged review/ADR gate, staged UI visual-state reentry | `X1` |
| compact single-session implementation, compact UI/visual/raster, compact owner packet, compact real-repo API migration, compact low-noise science/runtime | `X3` |
| pure scientific correctness without strict output budget | `X1` / `X3` near-tie |
| tuple-exact single-shot review/security/source investigation | `X1` / `X3` near-tie; N84 confirms exploit-reproduction security review still ties |
| compact real-repo patch when cost matters | `X3` with patch-hygiene guard; W47 ties binary but scores X3 higher |
| multi-file hidden-consumer migration | `X1` / `X3` binary near-tie; choose X3 for cost, X1 for hygiene |
| small test-led regression patch | `X1` / `X3` binary near-tie; choose X3 for cost after N71 |
| caller-spanning single-session API refactor | `X1` / `X3` binary near-tie; choose X3 for cost after N72, with explicit cache/scope hygiene guard |
| DOM event runtime UI correctness without strict output budget | `X1` / `X3` binary near-tie after N73; verify behavior on the target UI |
| DOM event runtime UI with strict output budget | `X3` primary after N74; X1 preserves runtime semantics but fails visible output budget |
| staged UI visual-state reentry | `X1` primary after N79; X3 completes the staged route but fails hidden state/accessibility/layout/raster/ledger/closure gates |
| calibrated actual screenshot grounding | `X1` primary after N80; X3 misses the match threshold and flags a false-positive header ornament |
| single-session persisted-state replay migration | `X1` / `X3` binary near-tie after N75; X2 also passes, so harden via staged re-entry or real repo constraints before assigning a primary |
| staged persisted-state replay migration | `X1` primary after N76; X3 fails runtime/schema/artifact contracts and X2 fails exact staged scope |
| single-session security implementation patch | `X1` / `X3` binary near-tie after N77; X3 has scored compactness edge, but no semantic security primary |
| staged security implementation / exploit re-entry | `X1` primary after N78; X3 fails hidden redirect exploit and staged artifact contracts, X2 fails scope/artifact layer |
| lower-bound calibration | `X2` first, `X6` second when route produces scoreable output |
| Gemini Pro | keep historical `X5` passes, but do not promote new claims until route/runtime health returns |

## Source

| Source | Role |
|---|---|
| `v2-core12-tie-hardened-results-2026-04-20.md` | admitted hardened core12 slots for `S03`, `S04`, `S05`, `S06`, `S07`, `S08`, `S09`, `S25`, `S27`, `N01`, `N02`, `N03`, `N04`, `N05`, `N06` |
| `role-fit-scorecard-v1-2026-04-22.md` | lane-fit interpretation and current hardening wave summaries |
| `short-results-current-2026-04-18.md` | compact operator-facing live status through `N84` |
| `../Evidence/x1-mainline-hardening-no-new-failures-2026-04-21.md` | admitted mainline hardening record |
| `../Evidence/n17-owner-routing-rubric-2026-04-22.json` through `../Evidence/n60-ui-reentry-rubric-2026-04-24.json` | machine-readable rubric/scorer evidence for promoted diagnostic slots |
| `../Evidence/n61-visual-pixel-localization-rubric-2026-04-25.json` | machine-readable `E51` visual pixel-localization diagnostic evidence; post-fix score favors `X1`, not promoted into `/40` |
| `../Evidence/n62-n63-frame-inversion-rubric-2026-04-25.json` | machine-readable `W41` frame-inversion diagnostic evidence; confirms execution-shape routing, not promoted into `/40` |
| `../Evidence/n64-security-depth-rubric-2026-04-25.json` | machine-readable `W42` security-depth diagnostic evidence; X1/X3 both pass, so not promoted into `/40` |
| `../Evidence/n65-visual-correctness-rubric-2026-04-25.json` | machine-readable `W43` visual-correctness diagnostic evidence; X1/X3 both pass, so not promoted into `/40` |
| `../Evidence/n66-conflicting-evidence-rubric-2026-04-25.json` | machine-readable `W44` conflicting-evidence diagnostic evidence; X1/X3 both pass, so not promoted into `/40` |
| `../Evidence/n67-cross-phase-integration-rubric-2026-04-25.json` | machine-readable `W45` cross-phase integration-owner diagnostic evidence; X1 passes and X3 fails scoreably, reinforcing staged owner/QA-gate routing but not promoted into `/40` |
| `../Evidence/n68-actual-screenshot-visual-review-rubric-2026-04-25.json` | machine-readable `W46` actual-screenshot visual grounding diagnostic evidence; both top rows fail, X3 has scored edge, not promoted into `/40` |
| `../Evidence/n69-patch-quality-rubric-2026-04-25.json` | machine-readable `W47` real-repo patch-quality scorecard evidence; X1 and X3 both pass hidden semantics, X3 wins cost score, X1 wins patch-hygiene score, not promoted into `/40` |
| `../Evidence/n70-entitlement-migration-rubric-2026-04-25.json` | machine-readable `W48` multi-file entitlement migration scorecard evidence; X1 and X3 both pass hidden schema-v2 consumers, X3 wins cost score, X1 wins patch-hygiene score, not promoted into `/40` |
| `../Evidence/n71-test-led-rubric-2026-04-25.json` | machine-readable `W49` test-led rate-limit regression scorecard evidence; X1 and X3 both pass behavior and required regression-test gates, X3 wins cost score, not promoted into `/40` |
| `../Evidence/n72-caller-refactor-rubric-2026-04-25.json` | machine-readable `W50` caller-spanning API refactor evidence; X1 and X3 both pass hidden API/service/CLI/report callers, X3 wins cost score, not promoted into `/40` |
| `../Evidence/n73-dom-runtime-rubric-2026-04-25.json` | machine-readable `W51` DOM event runtime UI evidence; X1 and X3 both pass runtime filter/keyboard/save behavior and tie rubric at `93 / 100`, not promoted into `/40` |
| `../Evidence/n74-dom-runtime-budget-rubric-2026-04-25.json` | machine-readable `W52` DOM runtime output-budget evidence; X1 passes runtime semantics but fails visible output budget, while X3 passes all gates, not promoted into `/40` |
| `../Evidence/n75-persisted-state-rubric-2026-04-25.json` | machine-readable `W53` persisted-state replay migration evidence; X1, X3, and X2 pass hidden semantics, X6 is runtime no-summary, not promoted into `/40` |
| `../Evidence/n76-staged-persisted-state-rubric-2026-04-25.json` | machine-readable `W54` staged persisted-state re-entry evidence; X1 passes, X3 scoreably fails, X2 scoreably fails exact staged scope, X6 is runtime no-summary, not promoted into `/40` |
| `../Evidence/n77-security-capability-rubric-2026-04-25.json` | machine-readable `W55` security capability runtime patch evidence; X1 and X3 both pass hidden exploit gates, X2 fails scoreably, X6 is runtime no-summary, not promoted into `/40` |
| `../Evidence/n78-staged-security-rubric-2026-04-25.json` | machine-readable `W56` staged security re-entry evidence; X1 passes, X3 fails scoreably, X2 fails scoreably, X6 is runtime no-summary, not promoted into `/40` |
| `../Evidence/n79-staged-ui-reentry-rubric-2026-04-28.json` | machine-readable `W57` staged UI visual-state reentry evidence; X1 passes, X3 fails scoreably, X4/Gemini not run by policy, not promoted into `/40` |
| `../Evidence/n80-screenshot-grounding-rubric-2026-04-28.json` | machine-readable `W58` calibrated screenshot-grounding evidence; X1 passes, X3 fails scoreably, X4/Gemini not run by policy, not promoted into `/40` |
| `../Evidence/n81-evidence-action-rubric-2026-04-28.json` | machine-readable `W59` evidence-conflict action-plan evidence; X1 and X3 both pass, so not promoted into `/40` |
| `../Evidence/n82-ux-state-rubric-2026-04-28.json` | machine-readable `W60` UX runtime-state evidence; X1 and X3 both pass, so not promoted into `/40` |
| `../Evidence/n83-interface-refactor-breakage-rubric-2026-04-28.json` | machine-readable `W61` interface-refactor breakage evidence; X1 and X3 both pass hidden batch-consumer and structured-report gates, so not promoted into `/40` |
| `../Evidence/n84-security-repro-rubric-2026-04-28.json` | machine-readable `W62` security-review reproduction evidence; X1 and X3 both pass exact JSON repro and false-positive gates, so not promoted into `/40` |
| `../Evidence/x4-full-v2-hard-2026-04-26.json` | machine-readable X4 final closing comparison evidence; `X4 / Claude China opus max` is `32 / 40` with `8` scoreable verifier failures and `0` runtime not-runs |
| `../Evidence/x2-x6-fill-full-v2-hard-2026-04-26.json` | machine-readable X2/X6 fill evidence; X2 is now closed at `12 / 40`, while X6 is `13 / 40` with `8` remaining timeout/auth-route `NOT-RUN` cells |

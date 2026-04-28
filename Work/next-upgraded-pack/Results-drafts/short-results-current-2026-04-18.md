Date: 2026-04-24
Owner: `$lead`
Status: `PASS`

## Result

This is the current compact operator read for the live benchmark state.

2026-04-24 update: active `X1` is now `gpt-5.5`. The fresh binary rerun over
`S01..S33 + N01..N41` passes `74 / 74` unique scenarios. The explicit `gpt-5.4 xhigh` hard-5
comparison also passes `5 / 5`; older `gpt-5.4` score and rubric rows otherwise remain model-of-run
historical evidence unless explicitly refreshed.

The old upgraded-pack tables remain the last full execution checkpoint for the legacy
upgraded-pack architecture only.
The expanded full `S01..S33 + N01..N07` surface below is now treated as a `DEPRECATED / SUPERSEDED`
pre-v3 ceiling-effect baseline, not as final classification evidence. V3 hardening replaces stale
lines in the current hardened live surface as scenario evidence is admitted.

Current canonical hardened classification lives in `full-v2-hard-results-current.md`. It preserves
the same `40` score-slot shape, but replaces the weak full-v2 cells with admitted hardened
equivalents across `12` routing lines plus one owner/control line.

| Row | Current `full-v2-hard` score | Current read |
|---|---:|---|
| `X1 / gpt-5.5` | `34 / 40` | second globally after N85 replacement; fails compact operator-budget slots, not hidden correctness |
| `X3 / opus 4.7max` | `35 / 40` | current top hardened row; fails staged re-entry/source-ledger slots |
| `X5 / gemini3.1pro` | `14 / 40` | partial only: `17` scoreable slots, `23` `NOT-RUN` |
| `X2 / gpt-spark` | `12 / 40` | closed lower-bound row: `12 PASS`, `28 FAIL`, `0 NOT-RUN` |
| `X6 / flash-lite` | `13 / 40` | partial lower-bound row: `13 PASS`, `18 FAIL`, `9 NOT-RUN`; remaining cells are timeout/auth-route requeues |

`Scenarios-v2` is quota-aware across the expanded full `S01..S33 + N01..N07` surface for
`X1`, `X2`, `X3`, `X4`, `X5`, and `X6`. Explicit provider quota / usage-limit failures are
`NOT-RUN` / `REQUEUE`, not scoreable `FAIL`. `X5` is currently route/runtime unhealthy for new
hardening waves: the latest wrapper and direct Gemini Pro probes timed out without an explicit quota
error; older admitted scoreable `X5` cells remain historical evidence.

`worker.long-autonomous` is now materialized as reference extra lane `E1` with `N08..N10`.
It is scored separately from the core `12` routing lanes. `X4` is held for the final closing
comparison run rather than per-wave hardening probes.

The previously tied core-12 lanes now also have a hardened targeted tiebreaker for `X1`, `X3`,
and `X5`. That tiebreaker separates `X5` lower on hardened review/security cases, but still does
not separate `X1` from `X3`.

Diagnostic `E2 top-pair-separator` (`N11..N13`) was also materialized and hardened in place.
The fresh 2026-04-21 separator slice added `N02` and `S30` hardening and ran `N02`, `S30`, and
`N11..N13` for both `X1` and `X3`. The binary gates remain tied at `5 / 5`; this overlay does not
add a binary top-pair ordering.

Diagnostic `E3 top-pair-rubric` now scores the fresh `N11..N13` outputs from that same run.
E3 gives a narrow diagnostic edge to `X1`: `60 / 60` versus `59 / 60`, caused only by `N13`
denominator-reporting wording.

Wave 4 then tightened the functional `S22 geometry-predicate-patch` oracle with adversarial
geometry cases. `X1` and `X3` both passed the extended truth table (`23 / 23` each), so
`binary tie remains`; `X4` and `X5` stay `NOT-RUN` for this pilot.

Option (c) then added `N14 multi-file-dependency-patch`, a new implementation scenario with
cross-file dependency coupling and decoy files. `X1` and `X3` both passed all 3 oracle behavior
cases and scope guards, so `binary tie remains` there too. Calibration on the same cell separates
`X2` lower as a scoreable `FAIL`; `X5` and `X6` are runtime `NOT-RUN` after no-output Gemini
timeouts.

`N15 stateful-batch-rollback-gauntlet` then changed the task class more radically: repeated
stateful API calls, checkpoint/resume, rollback, retry order, input immutability, and journal-based
reporting. `X1` and `X3` both passed the full invariant suite, so `binary tie remains` even on the
stateful gauntlet.

`N16 release-lane-integration-gauntlet` then added a larger long-horizon integration task and a
separate scored rubric. The binary gate still ties, but the diagnostic rubric separates by
efficiency: `X3 95 / 100` versus `X1 89 / 100`.

Calibration rows were then added on the same hardened separator surface. `X2` is scoreable and
separates lower at `1 / 5`; `X6` is scoreable and fails all five cells; `X5` does not currently
produce scoreable output because Gemini Pro times out before writing `worker-output.txt`, including
on a direct `OK` smoke prompt.

`X1/S16`, `X1/S19`, and `X1/S20` were rerun after the benchmark prompt override blocked
disposable-run `.reports/.plans` leakage. These three cells now supersede the old scope-drift
failures as `PASS`.

Diagnostic `E51` now materializes a pure visual pixel-localization gauntlet as `N61`: a
`2200 x 1600` raster with six `13 x 13` targets, same-color decoys, and point-distance scoring
with a several-pixel pass window. `N61` is not part of the `full-v2-hard` `/40` denominator. Current result:
the first raw `X1`/`X3` runs exposed an array prompt/schema defect, then the revised object-map
contract was rerun. Post-fix, `X1 / gpt-5.5`, `X3 / opus 4.7max`, and `X6 / gemini3.1flash-lite-preview`
all remain scoreable `FAIL` under the strict binary gate, but `X1` has the scored pixel-localization
edge (`65.1 / 100` versus `50.0 / 100` versus `40.0 / 100`). Official `X5 / gemini3.1pro` is runtime
`NOT-RUN` after a `600s` no-output timeout, and a separately labeled `gemini-3-flash-preview`
fallback diagnostic also timed out after `240s`.

W62 then added `N84-security-review-repro-gauntlet`: an ordinary security-review JSON report with
exact vuln tuples, exploit reproduction binding, false-positive suppression, and exact report scope.
`X1 / gpt-5.5` and `X3 / opus 4.7max` both passed with wrapper `0`; `binary tie remains`. This is
diagnostic evidence only and does not change the `full-v2-hard /40` denominator.

W63 added `N85-performance-review-runtime-budget` and promoted it over N59 in the canonical
`full-v2-hard /40`. N85 keeps hidden performance correctness/runtime/scope gates and adds hard
operator-output budget. `X1` scoreably fails only that budget (`266051 > 40000`) after passing
runtime/scope; `X3` passes all gates (`1827 <= 40000`). Current top-pair score is now
`X1 34 / 40` versus `X3 35 / 40`.

W65 through W67 added three diagnostic follow-ups outside the canonical `/40` denominator. N86
separates in favor of X1 on exact real interface migration surface after X3 passes hidden downstream
semantics but misses `api.py` scope. N87 ties on read-only performance review. N88 ties on UX
runtime event-policy simulation; X3 is much more compact, but no output budget is part of that
UX design contract.

W68 added `N89-security-review-runtime-witness-gauntlet` after v3 integrity hardening. Earlier
debug versions were not admitted because review found oracle/verifier answer leakage and weak
witness exactness. The admitted v3 run ties: `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass
executable witness binding at `100 / 100`; X3 is much more compact, but ordinary security review
remains top-pair near-tie.

| ID | Label |
|---|---|
| `X1` | `gpt-5.5` active; older rows may cite `gpt-5.4` as model-of-run |
| `X2` | `gpt-spark` |
| `X3` | `opus 4.7max` |
| `X4` | `Claude China` |
| `X5` | `gemini3.1pro` |
| `X6` | `gemini3.1flash-lite-preview` |

| `#` | Surface | `1` | `2` | `3` | `4` | `5` | `6` |
|---|---|---|---|---|---|---|---|
| `1` | steady-state core execution pack | `gpt-5.4` | `opus 4.7max` | `gpt-spark` |  |  |  |
| `2` | full execution-backed upgraded-pack registry | `gpt-5.4` | `opus 4.7max` | `gpt-spark` |  |  |  |
| `3` | pre-v3 full `Scenarios-v2` `S01..S33 + N01..N07` ceiling-effect baseline | `opus 4.7max` | `gpt-5.4` | `gemini3.1flash-lite-preview` | `Claude China` | `gpt-spark` | not final classification |
| `4` | full `Scenarios-v2` completed scoreable row below current cutoff | `gemini3.1pro` |  |  |  |  |  |
| `5` | reference extra lane `E1 worker.long-autonomous` on `N08..N10` | `opus 4.7max` | `gpt-5.4` | `gemini3.1pro` | `gemini3.1flash-lite-preview` | `gpt-spark` | `Claude China` is `NOT-RUN` |
| `6` | hardened core-12 weak-separator subset for `X1/X3/X5` | `opus 4.7max` | `gpt-5.4` | `gemini3.1pro` weaker with `12 PASS / 3 FAIL / 0 TIMEOUT` |  |  | targeted subset, not full-surface replacement |
| `7` | diagnostic hardened separator slice on `N02`, `S30`, and `N11..N13` | `gpt-5.4` tied with `opus 4.7max` | `opus 4.7max` tied with `gpt-5.4` |  |  |  | both `5 / 5` on fresh 2026-04-21 run |
| `8` | diagnostic `E3 top-pair-rubric` over fresh `N11..N13` outputs | `gpt-5.4` with `60 / 60` | `opus 4.7max` with `59 / 60` |  |  |  | diagnostic only, not a routing lane |
| `9` | Wave 4 functional `S22` adversarial geometry pilot | `gpt-5.4` tied with `opus 4.7max` | `opus 4.7max` tied with `gpt-5.4` |  | `Claude China` `NOT-RUN` | `gemini3.1pro` `NOT-RUN` | both `23 / 23`; `binary tie remains` |
| `10` | Option (c) implementation `N14` multi-file dependency pilot | `gpt-5.4` tied with `opus 4.7max` | `opus 4.7max` tied with `gpt-5.4` | `gpt-spark` scoreable `FAIL` | `Claude China` `NOT-RUN` | `gemini3.1pro` and `gemini3.1flash-lite-preview` runtime `NOT-RUN` | top pair both `3 / 3`; `X2 0 / 1`; Gemini `0 / 0` |
| `11` | `N15` stateful batch rollback gauntlet | `gpt-5.4` tied with `opus 4.7max` | `opus 4.7max` tied with `gpt-5.4` | `gpt-spark` `NOT-RUN` | `Claude China` `NOT-RUN` | Gemini rows `NOT-RUN` | top pair both `9 / 9`; `binary tie remains` |
| `12` | `N16` long-horizon release-lane integration rubric | `opus 4.7max` diagnostic edge | `gpt-5.4` second by rubric |  | `Claude China` `NOT-RUN` | Gemini rows `NOT-RUN` | binary top pair both `PASS`; rubric `X3 95 / 100`, `X1 89 / 100` |
| `13` | `N17` owner orchestration routing rubric | `gpt-5.4` tied with `opus 4.7max` | `opus 4.7max` tied with `gpt-5.4` | `gpt-spark` calibration `PASS` | `Claude China` `NOT-RUN` | `gemini3.1flash-lite-preview` calibration `PASS`; `gemini3.1pro` smoke `NOT-RUN` | all scoreable rows `100 / 100`; compactness favors `X3` and `X6` |
| `14` | `X1 / gpt-5.5` binary refresh on `S01..S33 + N01..N41` | `gpt-5.5` |  |  |  |  | `74 / 74` unique verifier PASS; `S13` clean retry supersedes earlier wrapper caveat; `N30` verifier PASS with wrapper caveat |
| `15` | hard-5 staged separator probe `N35,N36,N37,N39,N41` | `gpt-5.5` with `5 / 5`; explicit `gpt-5.4 xhigh` comparison also `5 / 5` | `Claude China` with `1 / 5` | `opus 4.7max`, official opus 4.5, and official opus 4.6 all `0 / 5` | official sonnet `0 / 3 scoreable` | official haiku `0 / 4 scoreable` | Sonnet/Haiku missing-summary cells are runtime-route, not model FAIL |
| `16` | W22/W23/W24 inverse-separator search on immutable tests and hidden interface consumers | `X1 / gpt-5.5`: `N42 PASS`, `N43 PASS`, `N44 PASS 96` | `X3 / opus 4.7max`: `N42 PASS`, `N43 PASS`, `N44 FAIL 72` |  |  |  | no honest `X1 FAIL / X3 PASS`; `N44` X3 failure is `.pytest_cache` changed-path scope hygiene, not hidden `sourceIds` semantics |
| `17` | W25 ownership-budget immutable report-consumer inverse probe | `X1 / gpt-5.5`: `N45 PASS 96` | `X3 / opus 4.7max`: `N45 PASS 100` |  |  |  | `binary tie remains`; X3 wins only by cost/output (`2628` bytes versus `180549`), not hidden replay/report semantics |
| `18` | W62 security review reproduction | `X1 / gpt-5.5`: `N84 PASS` | `X3 / opus 4.7max`: `N84 PASS` |  | `Claude China` final-only `NOT-RUN` | Gemini rows parked | `binary tie remains`; exact exploit reproduction and false-positive suppression did not split ordinary security review |
| `19` | W63 performance runtime budget replacement | `X1 / gpt-5.5`: `N85 FAIL`; output budget only | `X3 / opus 4.7max`: `N85 PASS` | `X2 FAIL`; no patch/runtime fail | `Claude China` final-only `NOT-RUN` | `X6 NOT-RUN`; Gemini `UNSUPPORTED_LOCATION`; X5 parked | promoted over N59; canonical top-pair now `X3 35 / 40` vs `X1 34 / 40` |
| `20` | W65 real interface downstream migration | `X1 / gpt-5.5`: `N86 PASS` | `X3 / opus 4.7max`: `N86 FAIL`; exact scope only | not launched | `Claude China` final-only `NOT-RUN` | Gemini rows parked | diagnostic only; X3 passed hidden downstream semantics but missed required `api.py` migration surface |
| `21` | W66 performance review gate | `X1 / gpt-5.5`: `N87 PASS` | `X3 / opus 4.7max`: `N87 PASS` | not launched | `Claude China` final-only `NOT-RUN` | Gemini rows parked | `binary tie remains`; benchmark admissibility and cache-boundary review did not split top pair |
| `18` | W26 operator-budget compact hotfix | `X1 / gpt-5.5`: `N46 FAIL 70` | `X3 / opus 4.7max`: `N46 PASS 100` |  |  |  | first honest compact single-session `X1 FAIL / X3 PASS`; X1 preserves hidden repair semantics but fails the visible operator-budget gate (`210369 > 40000`) |
| `19` | W27 UI compact operator-budget hotfix | `X1 / gpt-5.5`: `N47 FAIL 70` | `X3 / opus 4.7max`: `N47 PASS 94` |  |  |  | second honest compact single-session `X1 FAIL / X3 PASS`; both pass hidden UI dirty-state semantics and exact scope, while X1 fails the visible operator-budget gate (`169913 > 40000`) |
| `20` | W28 visual raster compact operator-budget hotfix | `X1 / gpt-5.5`: `N48 FAIL 70` | `X3 / opus 4.7max`: `N48 PASS 100` |  |  |  | third honest compact single-session `X1 FAIL / X3 PASS`; both pass exact raster semantics and renderer-only scope, while X1 fails the visible operator-budget gate (`77825 > 40000`) |
| `21` | W29 scientific compact operator-budget optimizer | `X1 / gpt-5.5`: `N49 PASS 96` | `X3 / opus 4.7max`: `N49 PASS 100` |  |  |  | `binary tie remains`; explicit operator budget did not separate the real MoM plus hydrogenic Schrodinger optimizer lane; X3 wins rubric by measured runtime only |
| `22` | W30 systems compact operator-budget hotfix | `X1 / gpt-5.5`: `N50 PASS 99` | `X3 / opus 4.7max`: `N50 PASS 99` |  |  |  | `binary tie remains`; explicit operator budget did not separate systems/toolchain immutable-CI hotfix, but X3 finished faster (`260.449s` versus `395.714s`) |
| `23` | W31 systems turnaround-budget hotfix | `X1 / gpt-5.5`: `N51 FAIL 70` | `X3 / opus 4.7max`: `N51 FAIL 55` |  |  |  | both scoreable `FAIL`; X1 preserves hidden systems semantics but fails output budget (`987540 > 40000`), while X3 stays compact/fast but fails hidden stagegate semantics |
| `24` | W32 interface-refactor compact operator-budget | `X1 / gpt-5.5`: `N52 FAIL 70` | `X3 / opus 4.7max`: `N52 FAIL 70` |  |  |  | both scoreable `FAIL`; X1 passes hidden interface semantics but fails output budget (`39316689 > 40000`), while X3 stays compact but fails `.pytest_cache` scope/shape hygiene |
| `25` | E51 visual pixel-localization diagnostic `N61` | `X1 / gpt-5.5`: `FAIL 65.1`; mean/max `77.065 / 106.231 px`; `6 / 6` ids | `X3 / opus 4.7max`: `FAIL 50.0`; mean/max `344.406 / 1981.709 px`; `6 / 6` ids, three within window |  |  | official `X5 / gemini3.1pro`: runtime `NOT-RUN`; `X6 / flash-lite`: `FAIL 40.0`, mean/max `363.604 / 1973.736 px` | not a `/40` slot; no binary winner; post-fix scored edge favors X1 for pure pixel localization |

| `#` | Legacy/pre-v3 rows note | Historical state |
|---|---|---|
| `1` | `X1 / gpt-5.5` | fresh 2026-04-24 binary refresh is `74 / 74` unique verifier PASS on `S01..S33 + N01..N41`; older `gpt-5.4` `39 / 40` full-v2 score is pre-v3 ceiling-effect baseline only |
| `2` | `X2 / gpt-spark` | usage-limit cells reran into scoreable results (`10 / 40`) |
| `3` | `X3 / opus 4.7max` | pre-v3 expanded full-v2 score was `40 / 40`; treat as ceiling-effect baseline, not final classification |
| `4` | `X4 / Claude China` | secret-backed route only; core quota cells reran as verifier-level failures (`10 / 40`); extra-lane `N08..N10` is deferred as `NOT-RUN` while route returns provider `502` |
| `5` | `X5 / gemini3.1pro` | quota reset and rerun completed; now scoreable across full surface (`34 / 40`) |
| `6` | `X6 / gemini3.1flash-lite-preview` | quota queue reran into scoreable results (`15 / 40`) |

| `#` | Extra-lane rows note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `3 / 3` on `N08..N10`; extended read `42 / 43` if combined with core `39 / 40` |
| `2` | `X2 / gpt-spark` | `1 / 3` on `N08..N10`; extended read `11 / 43` if combined with core `10 / 40` |
| `3` | `X3 / opus 4.7max` | `3 / 3` on `N08..N10`; extended read `43 / 43` if combined with core `40 / 40` |
| `4` | `X4 / Claude China` | `0 / 0`; `NOT-RUN`, do not combine into a `43` denominator until the secret route recovers |
| `5` | `X5 / gemini3.1pro` | `3 / 3` on `N08..N10`; extended read `37 / 43` if combined with core `34 / 40` |
| `6` | `X6 / gemini3.1flash-lite-preview` | `2 / 3` on `N08..N10`; extended read `17 / 43` if combined with core `15 / 40` |

| `#` | Hardened core-12 tiebreaker note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `15 / 15` official scoreable pass on hardened tied subset |
| `2` | `X3 / opus 4.7max` | `15 / 15` official scoreable pass on hardened tied subset |
| `3` | `X5 / gemini3.1pro` | `12 PASS / 3 FAIL / 0 TIMEOUT`; former timeout cells closed as `N02 PASS`, `N03 FAIL`, `N04 PASS`, `N05 FAIL`, `N06 PASS` |

| `#` | Diagnostic E2 top-pair note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `5 / 5` on fresh hardened `N02`, `S30`, `N11`, `N12`, `N13` |
| `2` | `X3 / opus 4.7max` | `5 / 5` on fresh hardened `N02`, `S30`, `N11`, `N12`, `N13` |
| `3` | `X2 / gpt-5.3-codex-spark` | `1 / 5`; only `N13` passes |
| `4` | `X5 / gemini3.1pro` | `0 / 0 scoreable`; `S30`, `N02`, isolated `N13`, and direct smoke attempt timed out before worker output |
| `5` | `X6 / gemini3.1flash-lite-preview` | `0 / 5`; all five completed cells fail local verification |
| `6` | conclusion | no binary separation between `X1` and `X3`; `X2` and `X6` separate below; `X5` is runtime-blocked |

| `#` | Diagnostic E3 rubric note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `60 / 60` over fresh 2026-04-21 `N11..N13` outputs |
| `2` | `X3 / opus 4.7max` | `59 / 60` over fresh 2026-04-21 `N11..N13` outputs |
| `3` | conclusion | supports only a narrow `X1` diagnostic edge; binary gates still tie |

| `#` | Wave 4 S22 adversarial geometry note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; `11 / 11` orientation cases and `12 / 12` segment cases; `wrapperExitCode=0` |
| `2` | `X3 / opus 4.7max` | `PASS`; `11 / 11` orientation cases and `12 / 12` segment cases; `wrapperExitCode=0` |
| `3` | `X4 / Claude China` | `NOT-RUN`; secret-backed route caveat unchanged |
| `4` | `X5 / gemini3.1pro` | `NOT-RUN`; Gemini Pro runtime caveat unchanged |
| `5` | conclusion | `binary tie remains`; next separator direction is Option (c), a new multi-file code patch scenario |

| `#` | Option (c) N14 multi-file dependency note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; `3 / 3` behavior cases; verifier `PASS`; scope guard `PASS`; `wrapperExitCode=0`; changed four source files plus tests |
| `2` | `X3 / opus 4.7max` | `PASS`; `3 / 3` behavior cases; verifier `PASS`; scope guard `PASS`; `wrapperExitCode=0`; changed four source files, tests unchanged |
| `3` | `X2 / gpt-spark` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `PASS`; failure reason was extra top-level `.reports` bundle entry |
| `4` | `X4 / Claude China` | `NOT-RUN`; route caveat unchanged |
| `5` | `X5 / gemini3.1pro` | runtime `NOT-RUN`; direct launch timed out at `900s`, stdin-null retry timed out at `600s`, no worker output or summary |
| `6` | `X6 / gemini3.1flash-lite-preview` | runtime `NOT-RUN`; direct launch timed out at `900s`, stdin-null retry timed out at `600s`, no worker output or summary |
| `7` | conclusion | `binary tie remains` for `X1`/`X3`; `X2` separates lower; Gemini rows are runtime-blocked, not model failures |

| `#` | N15 stateful gauntlet note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; full stateful invariant suite `9 / 9`; verifier `PASS`; scope guard `PASS`; `wrapperExitCode=0`; outer shell timed out before runner summary appeared, but the worker later completed scoreably |
| `2` | `X3 / opus 4.7max` | `PASS`; full stateful invariant suite `9 / 9`; verifier `PASS`; scope guard `PASS`; `wrapperExitCode=0` |
| `3` | conclusion | `binary tie remains`; even a stateful rollback/resume/retry gauntlet did not separate the top pair |

| `#` | N16 long-horizon rubric note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; integration verifier `10 / 10`; scope guard `PASS`; rubric `89 / 100`; patch-quality `30 / 30`; elapsed proxy `338.689s`; output-size cost proxy `393174` bytes |
| `2` | `X3 / opus 4.7max` | `PASS`; integration verifier `10 / 10`; scope guard `PASS`; rubric `95 / 100`; patch-quality `25 / 30`; elapsed proxy `502.532s`; output-size cost proxy `2829` bytes |
| `3` | conclusion | `binary tie remains`; diagnostic scored separation favors `X3` by `6` points on long-horizon integration efficiency, mostly from much lower output-size cost |

| `#` | N17 owner orchestration note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; owner routing verifier `PASS`; scope guard `PASS`; rubric `100 / 100`; elapsed proxy `121.745s`; output-size cost proxy `97344` bytes |
| `2` | `X3 / opus 4.7max` | `PASS`; owner routing verifier `PASS`; scope guard `PASS`; rubric `100 / 100`; elapsed proxy `116.485s`; output-size cost proxy `1965` bytes |
| `3` | `X2 / gpt-spark` | calibration `PASS`; rubric `100 / 100`; elapsed proxy `33.741s`; output-size cost proxy `81627` bytes |
| `4` | `X6 / gemini3.1flash-lite-preview` | calibration `PASS`; rubric `100 / 100`; elapsed proxy `58.275s`; output-size cost proxy `977` bytes |
| `5` | `X5 / gemini3.1pro` | runtime `NOT-RUN`; direct smoke timed out at `180s` without writing `x5-output.txt`; no semantic N17 run launched |
| `6` | conclusion | owner-boundary packet is not a top-pair separator; compactness favors `X3` among top pair and `X6` among calibration rows |

| `#` | N18 scientist/constraints note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; constraint decision verifier `PASS`; scope guard `PASS`; rubric `100 / 100`; elapsed proxy `124.214s`; output-size cost proxy `93786` bytes |
| `2` | `X3 / opus 4.7max` | `PASS`; constraint decision verifier `PASS`; scope guard `PASS`; rubric `100 / 100`; elapsed proxy `181.701s`; output-size cost proxy `2122` bytes |
| `3` | `X2 / gpt-spark` | calibration `PASS`; rubric `100 / 100`; elapsed proxy `36.402s`; output-size cost proxy `67739` bytes |
| `4` | `X6 / gemini3.1flash-lite-preview` | runtime `ROUTE-FAIL`; Gemini CLI hit missing `run_shell_command` / `AbortError`; partial artifact rubric `60 / 100`, not a model-quality fail |
| `5` | `X5 / gemini3.1pro` | runtime `NOT-RUN`; direct smoke wrote `X5_SMOKE_OK`, but semantic N18 run timed out at `900s` without summary or worker output |
| `6` | conclusion | `binary tie remains`; scientist/constraints correctness ties `X1`/`X3`, while compactness again favors `X3` |

| `#` | N19 systems/toolchain note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; toolchain verifier `PASS`; scope guard `PASS`; rubric `86 / 100`; patch-quality `30 / 30`; elapsed proxy `295.278s`; output-size cost proxy `281440` bytes |
| `2` | `X3 / opus 4.7max` | `PASS`; toolchain verifier `PASS`; scope guard `PASS`; rubric `95 / 100`; patch-quality `25 / 30`; elapsed proxy `201.068s`; output-size cost proxy `2786` bytes |
| `3` | `X2 / gpt-spark` | calibration `PASS`; rubric `84 / 100`; elapsed proxy `63.006s`; output-size cost proxy `215440` bytes |
| `4` | `X6 / gemini3.1flash-lite-preview` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `PASS`; missed portable cache key and source-trace report; rubric `65 / 100` |
| `5` | `X5 / gemini3.1pro` | `NOT-RUN` on N19; skipped after the immediately preceding semantic N18 timeout at `900s` without summary/output |
| `6` | conclusion | `binary tie remains` for `X1`/`X3`, but systems/toolchain role-fit now favors `X3` by `9` rubric points; `X6` separates lower scoreably |

| `#` | N20 UI interaction note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; UI verifier `PASS`; scope guard `PASS`; rubric `87 / 100`; patch-quality `28 / 30`; elapsed proxy `155.955s`; output-size cost proxy `126621` bytes |
| `2` | `X3 / opus 4.7max` | `PASS`; UI verifier `PASS`; scope guard `PASS`; rubric `95 / 100`; patch-quality `28 / 30`; elapsed proxy `250.417s`; output-size cost proxy `1406` bytes |
| `3` | `X2 / gpt-spark` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `PASS`; created forbidden top-level `.reports/`; rubric `57 / 100` |
| `4` | `X6 / gemini3.1flash-lite-preview` | runtime `ROUTE-FAIL`; Gemini route/tool abort with partial patch that missed disabled focus, filter stability, escape restore, visible return cue, and CSS stability |
| `5` | `X5 / gemini3.1pro` | `NOT-RUN` on N20; skipped after recent semantic N18 timeout |
| `6` | conclusion | `binary tie remains` for `X1`/`X3`, but UI implementation role-fit favors `X3` by `8` rubric points; `X2` and `X6` separate lower |

| `#` | W2 / N22 numerical stability note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; numerical verifier `PASS`; scope guard `PASS`; rubric `100 / 100`; elapsed proxy `161.522s`; output-size cost proxy `135379` bytes |
| `2` | `X3 / opus 4.7max` | `PASS`; numerical verifier `PASS`; scope guard `PASS`; rubric `99 / 100`; elapsed proxy `280.685s`; output-size cost proxy `2266` bytes |
| `3` | `X2 / gpt-spark` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `PASS`; no candidate files changed; rubric `10 / 100` |
| `4` | `X6 / gemini3.1flash-lite-preview` | runtime `ROUTE-FAIL`; Gemini route/tool abort with partial witness errors; not a model-quality fail |
| `5` | `X5 / gemini3.1pro` | `NOT-RUN` on N22; skipped pending fresh smoke-output because recent semantic Gemini Pro runs timed out |
| `6` | conclusion | `binary tie remains` for `X1`/`X3`; N22 gives X1 a one-point elapsed-score edge, while X3 keeps a much stronger compactness edge; X2 separates lower scoreably |

| `#` | W3 / N23 owner recovery note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; owner recovery verifier `PASS`; scope guard `PASS`; rubric `90 / 100`; elapsed proxy `124.862s`; output-size cost proxy `89826` bytes |
| `2` | `X3 / opus 4.7max` | `PASS`; owner recovery verifier `PASS`; scope guard `PASS`; rubric `100 / 100`; elapsed proxy `239.588s`; output-size cost proxy `1994` bytes |
| `3` | `X2 / gpt-spark` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `PASS`; created forbidden top-level `.reports`; rubric `70 / 100` |
| `4` | `X6 / gemini3.1flash-lite-preview` | runtime `ROUTE-FAIL`; Gemini route/tool abort with partial owner packet; not a model-quality fail |
| `5` | `X5 / gemini3.1pro` | `NOT-RUN` on N23; skipped pending fresh smoke-output |
| `6` | conclusion | `binary tie remains` for `X1`/`X3`, but owner recovery role-fit now favors `X3` by `10` rubric points; X2/X6 separate lower |

| `#` | W1 / N21 visual raster note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS`; visual raster verifier `PASS`; scope guard `PASS`; rubric `89 / 100`; elapsed proxy `143.817s`; output-size cost proxy `113449` bytes |
| `2` | `X3 / opus 4.7max` | `PASS`; visual raster verifier `PASS`; scope guard `PASS`; rubric `100 / 100`; elapsed proxy `191.406s`; output-size cost proxy `2175` bytes |
| `3` | `X2 / gpt-spark` | calibration `PASS`; verifier `PASS`; scope guard `PASS`; rubric `85 / 100`; tests unchanged |
| `4` | `X5 / gemini3.1pro` | runtime `RUNTIME-FAIL`; same-session smoke wrote `X5_SMOKE_OK`, but semantic N21 run timed out without `summary.json` or `worker-output.txt` |
| `5` | `X6 / gemini3.1flash-lite-preview` | runtime `RUNTIME-FAIL`; semantic N21 run timed out without `summary.json` or `worker-output.txt` |
| `6` | conclusion | `binary tie remains` for `X1`/`X3`; visual correctness ties, but compactness/cost favors `X3`; Gemini visual preference remains unproven |

| `#` | W4 / N24 systems-toolchain repeat note | Current state |
|---|---|---|
| `1` | `X3 / opus 4.7max` | `PASS`; stagegate verifier `PASS`; scope guard `PASS`; rubric `95 / 100`; elapsed proxy `233.975s`; output-size cost proxy `2705` bytes |
| `2` | `X1 / gpt-5.4` | `PASS`; stagegate verifier `PASS`; scope guard `PASS`; rubric `86 / 100`; elapsed proxy `371.585s`; output-size cost proxy `363208` bytes |
| `3` | `X2 / gpt-spark` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `PASS`; forbidden top-level `.reports` bundle-shape drift; rubric `54 / 100` |
| `4` | `X5 / gemini3.1pro` | scoreable `FAIL` after direct smoke `X5_SMOKE_OK`; missed cache-restore reason and summary source trace; rubric `65 / 100` |
| `5` | `X6 / gemini3.1flash-lite-preview` | scoreable `FAIL`; missed env fallback, dependency order, fingerprint portability, conflicts, and trace; rubric `65 / 100` |
| `6` | conclusion | `binary tie remains` for `X1`/`X3`, but N24 repeats the N19 systems/toolchain split: `X3 95 / 100` versus `X1 86 / 100`; systems/toolchain can move to `X3 primary`, `X1 secondary` |

| `#` | W4 / N25 UI dirty-state repeat note | Current state |
|---|---|---|
| `1` | `X5 / gemini3.1pro` | `PASS` after direct smoke `X5_SMOKE_OK`; UI dirty-state verifier `PASS`; scope guard `PASS`; rubric `98 / 100`; elapsed proxy `181.236s`; output-size cost proxy `873` bytes |
| `2` | `X3 / opus 4.7max` | `PASS`; UI dirty-state verifier `PASS`; scope guard `PASS`; rubric `97 / 100`; elapsed proxy `377.336s`; output-size cost proxy `2293` bytes |
| `3` | `X1 / gpt-5.4` | `PASS`; UI dirty-state verifier `PASS`; scope guard `PASS`; rubric `86 / 100`; elapsed proxy `277.103s`; output-size cost proxy `194944` bytes |
| `4` | `X2 / gpt-spark` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `PASS`; no candidate edits and forbidden top-level `.reports`; rubric `43 / 100` |
| `5` | `X6 / gemini3.1flash-lite-preview` | runtime `ROUTE-FAIL`; Gemini missing-tool loop / `AbortError`; partial patch not scoreable |
| `6` | conclusion | `binary tie remains` for `X1`/`X3`, but N25 repeats the N20 UI split: `X3` beats `X1`; `X5` is a strong UI contender after a healthy semantic pass |

| `#` | W6 / N26 owner recovery repeat note | Current state |
|---|---|---|
| `1` | `X3 / opus 4.7max` | `PASS`; owner wave verifier `PASS`; scope guard `PASS`; rubric `100 / 100`; elapsed proxy `274.897s`; output-size cost proxy `2488` bytes |
| `2` | `X5 / gemini3.1pro` | `PASS` after direct smoke `X5_SMOKE_OK`; owner wave verifier `PASS`; scope guard `PASS`; rubric `100 / 100`; elapsed proxy `150.840s`; output-size cost proxy `766` bytes |
| `3` | `X1 / gpt-5.4` | `PASS`; owner wave verifier `PASS`; scope guard `PASS`; rubric `92 / 100`; elapsed proxy `137.357s`; output-size cost proxy `119280` bytes |
| `4` | `X2 / gpt-spark` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `PASS`; stale markers/lane-state misses; rubric `70 / 100` |
| `5` | `X6 / gemini3.1flash-lite-preview` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `PASS`; incomplete owner packet despite small output; rubric `50 / 100` |
| `6` | conclusion | `binary tie remains` for `X1`/`X3`, but N26 repeats N23: `X3` beats `X1`; `X5` is a serious owner contender after a healthy semantic pass |

| `#` | W7 / N27 long-horizon release-train repeat note | Current state |
|---|---|---|
| `1` | `X3 / opus 4.7max` | `PASS`; release-train verifier `PASS`; scope guard `PASS`; rubric `92 / 100`; elapsed proxy `821.310s`; output-size cost proxy `3537` bytes |
| `2` | `X1 / gpt-5.4` | `PASS`; release-train verifier `PASS`; scope guard `PASS`; rubric `88 / 100`; elapsed proxy `438.414s`; output-size cost proxy `487950` bytes |
| `3` | `X2 / gpt-spark` | calibration `PASS`; release-train verifier `PASS`; scope guard `PASS`; rubric `88 / 100`; high output cost proxy `660126` bytes |
| `4` | `X6 / gemini3.1flash-lite-preview` | runtime `ROUTE-FAIL`; wrapper `1` with Gemini quota/tool-loop/`AbortError`; partial candidate missed verifier invariants and is not model-quality FAIL |
| `5` | `X5 / gemini3.1pro` | runtime `REQUEUE`; same-session smoke failed with quota and did not write `X5_SMOKE_OK`; semantic N27 run not launched |
| `6` | conclusion | `binary tie remains` for `X1`/`X3`, but N27 repeats N16's compact long-horizon split: `X3` beats `X1`; `X2` passes as calibration only |

| `#` | W8 / N28 incident-driven integration repair note | Current state |
|---|---|---|
| `1` | `X3 / opus 4.7max` | `PASS`; incident repair verifier `PASS`; scope guard `PASS`; rubric `99 / 100`; elapsed proxy `932.627s`; output-size cost proxy `3057` bytes; tests and reconciliation note changed |
| `2` | `X1 / gpt-5.4` | `PASS`; incident repair verifier `PASS`; scope guard `PASS`; rubric `93 / 100`; elapsed proxy `419.507s`; output-size cost proxy `304834` bytes; reconciliation note changed, tests unchanged |
| `3` | `X2 / gpt-spark` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `PASS`; no candidate edits; rubric `16 / 100`; failed runtime and reconciliation invariants |
| `4` | `X6 / gemini3.1flash-lite-preview` | runtime `ROUTE-FAIL`; wrapper `1` with Gemini quota/tool-loop/`AbortError`; partial patch failed runtime invariants and is not model-quality FAIL |
| `5` | `X5 / gemini3.1pro` | runtime `REQUEUE`; two same-session direct smoke attempts timed out without writing `X5_SMOKE_OK`; semantic N28 run not launched |
| `6` | conclusion | `binary tie remains` for `X1`/`X3`, but N28 strengthens the cross-role integration read: `X3 99 / 100` beats `X1 93 / 100`; `X2` separates lower scoreably |

| `#` | W9 / N29 ownership-budget incident repair note | Current state |
|---|---|---|
| `1` | `X3 / opus 4.7max` | `PASS`; ownership-budget verifier `PASS`; exact patch-budget scope `PASS`; rubric `100 / 100`; elapsed proxy `694.629s`; output-size cost proxy `2325` bytes |
| `2` | `X1 / gpt-5.4` | `PASS`; ownership-budget verifier `PASS`; exact patch-budget scope `PASS`; rubric `96 / 100`; elapsed proxy `228.279s`; output-size cost proxy `155704` bytes |
| `3` | `X2 / gpt-spark` | scoreable `FAIL`; wrapper `0`, verifier `FAIL`, scope guard `FAIL`; no candidate edits; rubric `42 / 100` |
| `4` | `X6 / gemini3.1flash-lite-preview` | runtime `RUNTIME-FAIL`; semantic run timed out without `summary.json` or `worker-output.txt`; not model-quality FAIL |
| `5` | `X5 / gemini3.1pro` | runtime `REQUEUE`; direct smoke timed out without writing `X5_SMOKE_OK`; semantic N29 run not launched |
| `6` | conclusion | `binary tie remains` for `X1`/`X3` even under exact four-path patch budget; `X3` still wins cost-only rubric, and `X2` separates lower scoreably |

| `#` | Hardened N06 tuple-exact note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS` on hardened `N06`; 3 of 3 required tuples match; no forbidden-trap rows; `wrapperExitCode=0` |
| `2` | `X3 / opus 4.7max` | `PASS` on hardened `N06`; 3 of 3 required tuples match; no forbidden-trap rows; `wrapperExitCode=0` |
| `3` | conclusion | `binary tie remains`; tuple-exact verifier blocked compliance-retelling but both near-ceiling models produced legitimate tuples |

| `#` | Hardened wave 2 tuple-exact note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS` on all five hardened cells (`S27`, `S28`, `S29`, `N05`, `N07`); 17 of 17 required tuples match across the wave; no forbidden-trap rows; `wrapperExitCode=0` for each |
| `2` | `X3 / opus 4.7max` | `PASS` on all five hardened cells; 17 of 17 required tuples match; no forbidden-trap rows; `wrapperExitCode=0` for each |
| `3` | conclusion | `binary tie remains` on every wave-2 cell; combined with `N06` the tuple-exact template now covers `6` hardened review cells, all tied; leak removal closed the compliance-retelling path but did not unlock near-ceiling separation on review-class tasks |

| `#` | Hardened wave 3 S06 tuple-exact note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | `PASS` on hardened `S06` repository investigation; 4 of 4 confirmed facts, 4 of 4 false leads, 2 of 2 unknowns all match; `wrapperExitCode=0` |
| `2` | `X3 / opus 4.7max` | `PASS` on hardened `S06`; 4 of 4 confirmed facts, 4 of 4 false leads, 2 of 2 unknowns all match; `wrapperExitCode=0` |
| `3` | conclusion | `binary tie remains` on `S06`; both models investigated the repo slice and produced correct tuples despite the abstract `noisy-intake-notes.md` giving no filenames; combined with waves 1 + 2 the tuple-exact template now covers `7` cells, every one tied at PASS/PASS across both review-class and factual-investigation surfaces |

| `#` | Caveat | Applies to |
|---|---|---|
| `1` | the live v2 surface now includes routing-basis `N01..N07`; compare against the earlier `S01..S33` read only with the surface change in mind | full v2 surface |
| `2` | `X4` current read is valid only on the repo-canonical secret-backed Claude path; earlier same-day non-secret and broken-path attempts are not part of the admitted table. The admitted `full-v2-hard` closing run is `32 / 40` with `8` scoreable verifier failures and `0` runtime not-runs | `Claude China` |
| `3` | `X5` no longer has quota `REQUEUE`; `S12` reran into scoreable `FAIL` after earlier timeout attempts | `gemini3.1pro` |
| `4` | `X6` current read merges the completed fallback full-surface root with quota-rerun roots from `2026-04-19`; already scoreable original passes were not overwritten by later noisy reruns | `gemini3.1flash-lite-preview` |
| `5` | `S25` and `S26` were re-audited before this read; tamper checks now fail on metadata drift and protected-surface edits | review-bundle integrity |
| `6` | `N08..N10` are an extra-lane score, not a core `12`-lane rerank; `X4` extra-lane cells are excluded from scoring because the required route did not produce a clean attempt | `worker.long-autonomous` |
| `7` | the hardened core-12 tiebreaker is not merged into the full `40` denominator because those contracts/verifiers changed after the full-surface run; `X5` timeout cells are now closed inside that targeted evidence only | targeted `X1/X3/X5` tiebreaker |
| `8` | diagnostic hardened separator slice is not a routing lane and should not be promoted into `externalPriorityProfiles`; it is only evidence that current binary gates still do not separate the top pair | `X1/X3` top-pair separator |
| `9` | diagnostic `E3` is a rubric over generated outputs, not a verifier pass/fail result | `X1/X3` top-pair rubric |
| `10` | `X1/S16`, `X1/S19`, and `X1/S20` old failures were superseded by the control-plane override rerun; this updates the full-v2 `X1` read from `36 / 40` to `39 / 40` | `gpt-5.4` |
| `11` | `N06` was rebuilt in place on `2026-04-21` with a tuple-exact contract and a removed `inputs/review-observations.md` answer-leak file; the pre-v3 `N06` binary score on the full-v2 baseline is a ceiling-artefact for this cell only and must not be compared against the hardened read without noting the contract change | `N06 authz-trust-boundary-review` |
| `12` | `X1 attempt 1` on hardened `N06` stalled at codex `stdin` read under `run_in_background` and was killed after `17 min / 0.03s CPU`; the admitted `X1 N06` result uses `attempt 3` launched through `cmd /c "pwsh ... < NUL"`; this is a runtime invocation footnote, not a model or verifier failure | `N06 X1 runtime lineage` |
| `13` | `S27`, `S28`, `S29`, `N05`, and `N07` were rebuilt in place on `2026-04-21` using the same tuple-exact template as `N06`; pre-v3 scores for those five cells on the full-v2 baseline are ceiling-artefacts for those cells only and must not be compared against the hardened reads without noting the contract change | `wave 2 review cells` |
| `14` | the wave-2 verifier parser now honors `\|` escape and merges trailing cells back into the last column when a candidate's Evidence cell contains raw `\|\|`; this makes the verifier robust to JS code snippets in Evidence without forcing candidates to escape pipes, closing a real failure mode uncovered during pre-run dry-run | `wave 2 verifier robustness` |
| `15` | `X1 wave 2` was launched as five independent single-scenario background tasks through `cmd /c "pwsh -File ... -ScenarioIds S27 < NUL"` per cell; the one-shot comma-joined form `cmd /c "pwsh -File ... -ScenarioIds S27,S28,S29,N05,N07"` loses the array across the cmd-to-pwsh boundary when `-File` mode binds the whole comma-joined token as a single scenario id; this is a launch-wrapper footnote, not a model or verifier failure | `wave 2 X1 launch lineage` |
| `16` | `S06` was rebuilt in place on `2026-04-21` using the tuple-exact template adapted for repository investigation — three separate match tables (`Confirmed Facts`, `False Leads Rejected`, `Explicit Unknowns`) instead of one `Findings` table; `candidate/repo-snapshot/` preserved unchanged; pre-v3 `S06` score is a ceiling-artefact for that cell only and must not be compared against the hardened read without noting the contract change | `S06 wave 3` |
| `17` | `S22` was tightened in place on `2026-04-21` by extending `oracle/truth-table.json` from `11` to `23` functional cases and keeping `candidate/**` unchanged in mainline; the admitted run is diagnostic only and does not merge into the old full-v2 denominator | `S22 wave 4` |
| `18` | `N14` was added on `2026-04-21` as a new diagnostic implementation pilot with cross-file dependency coupling; it is not merged into the old full-v2 denominator; `X1`/`X3` tie, `X2` scoreably fails, and `X5`/`X6` are runtime `NOT-RUN` | `N14 Option (c)` |
| `19` | `N15` was added on `2026-04-21` as a diagnostic stateful implementation gauntlet; it is not merged into the old full-v2 denominator; `X1` and `X3` both pass all stateful invariants | `N15 stateful gauntlet` |
| `20` | `N16` was added on `2026-04-22` as a diagnostic long-horizon integration task with an explicit non-binary rubric; it is not merged into the old full-v2 denominator; `X1` and `X3` both pass the binary gate, while the rubric reads `X3 95 / 100` and `X1 89 / 100` | `N16 long-horizon rubric` |
| `21` | `N17` was added on `2026-04-22` as a diagnostic owner/orchestration routing task with calibration rows; it is not merged into the old full-v2 denominator; `X1`, `X2`, `X3`, and `X6` all pass and score `100 / 100`, while `X5` is runtime `NOT-RUN` after failed smoke | `N17 owner orchestration` |
| `22` | `N18` was added on `2026-04-22` as a diagnostic scientist/constraints decision task with calibration rows; it is not merged into the old full-v2 denominator; `X1`, `X2`, and `X3` pass and score `100 / 100`; `X6` is runtime `ROUTE-FAIL`; `X5` is runtime `NOT-RUN` after semantic timeout | `N18 scientist constraints` |
| `23` | `N19` was added on `2026-04-22` as a diagnostic systems/toolchain implementation task with calibration rows; it is not merged into the old full-v2 denominator; `X1`, `X2`, and `X3` pass; `X3` has the strongest rubric read at `95 / 100`; `X6` is a scoreable verifier `FAIL`; `X5` is `NOT-RUN` | `N19 systems toolchain` |
| `24` | `N20` was added on `2026-04-22` as a diagnostic UI interaction implementation task with calibration rows; it is not merged into the old full-v2 denominator; `X1` and `X3` pass; `X3` has the strongest rubric read at `95 / 100`; `X2` scoreably fails and `X6` route-fails | `N20 UI interaction` |
| `25` | `N22` was added on `2026-04-22` as W2/E12 numerical-stability constraint task with exact JSON witnesses; it is not merged into the old full-v2 denominator; `X1` and `X3` pass; `X1` reads `100 / 100`, `X3` reads `99 / 100`; `X2` scoreably fails and `X6` route-fails | `N22 numerical stability` |
| `26` | `N23` was added on `2026-04-22` as W3/E13 owner-recovery stale-source routing task; it is not merged into the old full-v2 denominator; `X1` and `X3` pass; `X3` reads `100 / 100`, `X1` reads `90 / 100`; `X2` scoreably fails and `X6` route-fails | `N23 owner recovery` |
| `27` | `N21` was added on `2026-04-22` as W1/E11 visual-raster provider-fit task; it is not merged into the old full-v2 denominator; `X1`, `X2`, and `X3` pass; `X3` reads `100 / 100`, `X1` reads `89 / 100`, `X2` reads `85 / 100`; `X5` and `X6` are runtime no-summary timeouts after launch | `N21 visual raster` |
| `28` | `N24` was added on `2026-04-22` as W4/E14 systems-toolchain repeat; it is not merged into the old full-v2 denominator; `X1` and `X3` pass; `X3` reads `95 / 100`, `X1` reads `86 / 100`; `X2`, `X5`, and `X6` are scoreable verifier failures | `N24 systems repeat` |
| `29` | `N25` was added on `2026-04-22` as W4/E15 UI dirty-state repeat; it is not merged into the old full-v2 denominator; `X1`, `X3`, and `X5` pass; `X5` reads `98 / 100`, `X3` reads `97 / 100`, `X1` reads `86 / 100`; `X2` scoreably fails and `X6` route-fails | `N25 UI dirty state` |
| `30` | `N26` was added on `2026-04-22` as W6/E16 owner recovery repeat; it is not merged into the old full-v2 denominator; `X1`, `X3`, and `X5` pass; `X3` and `X5` read `100 / 100`, `X1` reads `92 / 100`; `X2` and `X6` scoreably fail | `N26 owner recovery repeat` |
| `31` | `N27` was added on `2026-04-22` as W7/E17 long-horizon release-train repeat; it is not merged into the old full-v2 denominator; `X1`, `X2`, and `X3` pass; `X3` reads `92 / 100`, `X1` and `X2` read `88 / 100`; `X6` route-fails and `X5` requeues after quota-gated smoke | `N27 long-horizon repeat` |
| `32` | `N28` was added on `2026-04-22` as W8/E18 incident-driven cross-role integration repair; it is not merged into the old full-v2 denominator; `X1` and `X3` pass; `X3` reads `99 / 100`, `X1` reads `93 / 100`; `X2` scoreably fails, `X6` route-fails, and `X5` requeues after smoke timeouts | `N28 incident repair` |
| `33` | `N29` was added on `2026-04-23` as W9/E19 ownership-budget incident repair; it is not merged into the old full-v2 denominator; `X1` and `X3` pass exact runtime and patch-budget gates; `X3` reads `100 / 100`, `X1` reads `96 / 100`; `X2` scoreably fails, `X6` times out without summary, and `X5` requeues after smoke timeout | `N29 ownership budget` |
| `34` | `N30` was added on `2026-04-23` as W10/E20 staged delivery re-entry; it is not merged into the old full-v2 denominator; `X1` passes, `X3` scoreably fails by omitting the `03-review-response` persisted phase ledger, `X2` scoreably fails after forbidden `.reports` bundle drift, `X6` times out without final summary, and `X5` requeues after smoke timeout | `N30 staged re-entry` |
| `35` | `N31` was added on `2026-04-23` as W11/E21 computational electromagnetics hardening; it is not merged into the old full-v2 denominator; `X1` and `X3` both pass the MoM PEC-cylinder solver with cylindrical-harmonic analytical oracle; `X3` reads `94 / 100`, `X1` reads `92 / 100`; `X5` and `X6` were not launched under the updated calibration rule | `N31 MoM analytical oracle` |
| `36` | `N32` was added on `2026-04-23` as W12/E22 dual-physics analytical-oracle hardening; it is not merged into the old full-v2 denominator; one task combines MoM PEC-cylinder surface-density/field checks with hydrogenic radial Schrodinger finite-difference checks and solver-runtime scoring; `X1` and `X3` both pass, `X3 100 / 100`, `X1 97 / 100`; `X2` scoreably fails at `33 / 100`; `X6` is runtime no-summary after timeout; `X5` requeues because direct smoke did not write `X5_SMOKE_OK` | `N32 dual physics oracle` |
| `37` | `N33` was added on `2026-04-23` as W13/E23 interface-refactor breakage hardening; it is not merged into the old full-v2 denominator; `X1` and `X3` both pass the structured interface migration and hidden-consumer verifier, `X3 100 / 100`, `X1 96 / 100`; `X2` scoreably fails at `5 / 100`; `X6` timed out without `summary.json`; `X5` stayed route-gated `REQUEUE` | `N33 interface refactor` |
| `38` | `N34` was added on `2026-04-23` as W14/E24 high-load science optimizer hardening; it is not merged into the old full-v2 denominator; `X1` and `X3` both pass the staged MoM plus hydrogenic radial Schrodinger performance verifier, both read `96 / 100`; X1 is faster on measured solver runtime, X3 is much more compact; `X2` scoreably fails at `27 / 100`; Gemini rows stayed route caveats | `N34 high-load science optimizer` |
| `39` | `N35` was added on `2026-04-23` as W15/E25 staged interface-migration re-entry hardening; it is not merged into the old full-v2 denominator; `X1 PASS 96 / 100`, `X3 scoreable FAIL 71 / 100`, and `X2 PASS 91 / 100`; X3 failed hidden runtime semantics plus migration-ledger details with `wrapperExitCode=0`; `X5` and `X6` are runtime-route failures from Gemini quota/tool-loop/AbortError | `N35 staged interface migration` |
| `40` | `N36` was added on `2026-04-23` as W16/E26 real-repo staged API migration hardening; it is not merged into the old full-v2 denominator; `X1 PASS 97 / 100`, `X3 scoreable FAIL 74 / 100`, and `X2 scoreable FAIL 70 / 100`; X3 failed hidden API semantics plus migration-ledger details with `wrapperExitCode=0`; `X6` is runtime no-summary after phase-2 Gemini quota/stall and `X5` stayed smoke-gated | `N36 staged API migration` |
| `41` | `N37` was added on `2026-04-23` as W17/E27 staged adversarial review-gate hardening; it is not merged into the old full-v2 denominator; `X1 PASS 98 / 100`, `X3 scoreable FAIL 35 / 100`, and `X2 PASS 97 / 100`; X3 failed ADR source binding, exact finding/source-id tuples, non-claim ledger, response cues, and closure markers with `wrapperExitCode=0`; `X6` is runtime-route from Gemini quota/tool-loop/AbortError and `X5` stayed smoke-gated after direct Pro smoke timeout | `N37 staged review gate` |
| `42` | `N38` was added on `2026-04-23` as W18/E28 staged UI/visual/state integration hardening; it is not merged into the old full-v2 denominator; `X1 PASS 94 / 100`; `X2` scoreably fails at `78 / 100`; `X3` is `NOT-RUN` after three phase-4 no-summary stalls; `X5` and `X6` are runtime-route caveats | `N38 staged UI/visual/state` |
| `43` | `N39` was added on `2026-04-23` as W19/E29 staged systems/toolchain recovery re-entry hardening; it is not merged into the old full-v2 denominator; bounded-scope rerun reads `X1 PASS 94 / 100`, `X3` scoreable `FAIL 78 / 100`, `X2` scoreable `FAIL 76 / 100`, `X6` scoreable `FAIL 78 / 100`, and `X5` runtime-route; this is now a staged systems/toolchain separator in favor of `X1` | `N39 staged toolchain re-entry` |
| `44` | `N40` was added on `2026-04-23` as W20/E30 staged owner-recovery re-entry hardening; it is not merged into the old full-v2 denominator; `X1 PASS 98 / 100` versus `X3 scoreable FAIL 55 / 100`; `X2` scoreably fails at `78 / 100`, `X6` scoreably fails at `40 / 100`, and `X5` is runtime-route; staged owner recovery now reads `X1 primary` while single-session owner recovery still reads `X3 primary` | `N40 staged owner recovery` |
| `45` | `N41` was added on `2026-04-23` as W21/E31 staged incident-budget re-entry hardening; it is not merged into the old full-v2 denominator; `X1 PASS 100 / 100` versus `X3 scoreable FAIL 78 / 100`; `X2` scoreably fails at `78 / 100`; `X5` is runtime-route and `X6` is runtime no-summary; staged long-horizon / ownership-budget incident repair now reads `X1 primary` while compact single-session incident repair still reads `X3 primary` | `N41 staged incident-budget re-entry` |
| `46` | `N42` was added on `2026-04-24` as W22/E32 systems/toolchain immutable-CI hotfix; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass, both change only five production `src/stagegate/*.py` files, and visible tests are protected by scope/hash gates; `binary tie remains` | `N42 systems immutable-CI` |
| `47` | `N43` was added on `2026-04-24` as W23/E33 UI dirty-state immutable-test hotfix; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass, both change only three production UI files, and visible tests are protected by scope/hash gates; `binary tie remains` | `N43 UI immutable-test` |
| `48` | `N44` was added on `2026-04-24` as W24/E34 interface-refactor sourceId hidden-consumer hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` passes at `96 / 100`, while `X3 / opus 4.7max` scoreably fails at `72 / 100` because `.pytest_cache` files drift into the exact changed-path budget. Hidden interface/sourceId/report semantics pass for X3, so this is patch-hygiene separation, not an inverse semantic separator | `N44 interface sourceId hidden consumer` |
| `49` | `N45` was added on `2026-04-24` as W25/E35 ownership-budget immutable report-consumer hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass hidden replay/report-consumer gates with exact three-path budget. Rubric reads `X3 100 / 100` versus `X1 96 / 100` only from output cost; `binary tie remains` | `N45 ownership report consumer` |
| `50` | `N46` was added on `2026-04-24` as W26/E36 operator-budget compact hotfix hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` scoreably fails the visible operator-budget gate (`210369 > 40000`) while passing hidden ownership and exact-scope gates, and `X3 / opus 4.7max` passes all gates (`2378 <= 40000`). This is the first honest compact single-session `X1 FAIL / X3 PASS` separator, scoped to low-noise/operator-budget behavior rather than semantic repair correctness | `N46 operator-budget compact hotfix` |
| `51` | `N47` was added on `2026-04-24` as W27/E37 UI compact operator-budget hotfix hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` scoreably fails the visible operator-budget gate (`169913 > 40000`) while passing hidden UI dirty-state semantics and exact-scope gates, and `X3 / opus 4.7max` passes all gates (`2467 <= 40000`). This is the second honest compact single-session `X1 FAIL / X3 PASS` separator and the first on the UI implementation lane | `N47 UI operator-budget compact hotfix` |
| `52` | `N48` was added on `2026-04-24` as W28/E38 visual raster compact operator-budget hotfix hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` scoreably fails the visible operator-budget gate (`77825 > 40000`) while passing exact visual raster semantics and renderer-only scope, and `X3 / opus 4.7max` passes all gates (`813 <= 40000`). This is the third honest compact single-session `X1 FAIL / X3 PASS` separator and the first on the visual graphics lane | `N48 visual operator-budget compact hotfix` |
| `53` | `N49` was added on `2026-04-24` as W29/E39 scientific compact operator-budget optimizer hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass the full MoM PEC-cylinder plus hydrogenic radial Schrodinger optimizer verifier, exact scope, and visible operator budget. Rubric reads `X3 100 / 100` versus `X1 96 / 100` from measured solver runtime; `binary tie remains` | `N49 science operator-budget optimizer` |
| `54` | `N50` was added on `2026-04-24` as W30/E40 systems compact operator-budget hotfix hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass hidden stagegate systems semantics, protected visible CI hash, exact scope, and visible operator budget. Rubric ties at `99 / 100`; elapsed time favors X3 (`260.449s` versus `395.714s`) | `N50 systems operator-budget compact hotfix` |
| `55` | `N51` was added on `2026-04-24` as W31/E41 systems turnaround-budget hotfix hardening; it is not merged into the old full-v2 denominator; both top rows fail scoreably under the combined hidden semantics, output budget, and `360s` prompt-to-output SLA. `X1 / gpt-5.5` preserves hidden systems semantics but fails output budget at `987540` bytes; `X3 / opus 4.7max` stays compact and fast but fails hidden stagegate semantics. This is tradeoff evidence, not an inverse separator | `N51 systems turnaround-budget hotfix` |
| `56` | `N52` was added on `2026-04-24` as W32/E42 interface-refactor compact operator-budget hardening; it is not merged into the old full-v2 denominator; both top rows fail scoreably. `X1 / gpt-5.5` passes hidden interface-refactor semantics and exact required changed paths but fails the visible output budget at `39316689` bytes; `X3 / opus 4.7max` passes the output budget at `2573` bytes but fails scope/bundle-shape because `.pytest_cache` files drift into the copied bundle | `N52 interface-refactor operator-budget` |
| `57` | `N53` was added on `2026-04-24` as W33/E43 interface-refactor cache-ignored operator-budget hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass hidden interface-refactor semantics, exact required-path scope after top-level `.pytest_cache/**` is ignored as generated test cache, and visible operator budget. Rubric ties at `100 / 100`; `binary tie remains` | `N53 interface-refactor cache-ignored operator-budget` |
| `58` | `N54` was added on `2026-04-24` as W34/E44 release-train compact operator-budget hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` scoreably fails the visible operator-budget gate (`300873 > 40000`) while passing hidden release-train stateful semantics and exact scope, and `X3 / opus 4.7max` passes all gates (`2618 <= 40000`). This is the fourth compact single-session `X1 FAIL / X3 PASS` separator and the first on the release-train long-horizon line | `N54 release-train operator-budget compact` |
| `59` | `N55` was added on `2026-04-24` as W35/E45 incident compact operator-budget hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` scoreably fails the visible operator-budget gate (`352056 > 40000`) while passing hidden incident integration/reconciliation semantics and exact scope, and `X3 / opus 4.7max` passes all gates (`1841 <= 40000`). This is the fifth compact single-session `X1 FAIL / X3 PASS` separator and the first on the cross-role incident repair line | `N55 incident operator-budget compact` |
| `60` | `N56` was added on `2026-04-24` as W36/E46 owner-recovery compact operator-budget hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` scoreably fails the visible operator-budget gate (`135621 > 40000`) while passing hidden owner-recovery semantics and exact scope, and `X3 / opus 4.7max` passes all gates (`1220 <= 40000`). `X2` scoreably fails (`10 / 100`) after leaving the semantic packet missing/unchanged; `X6` is runtime `NOT-RUN` after no-summary timeout; `X5` is quota-deferred and `X4` stays final-only | `N56 owner operator-budget compact` |
| `61` | `N57` was added on `2026-04-24` as W37/E47 real-repo compact API migration operator-budget hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` scoreably fails the visible operator-budget gate (`3792275 > 40000`) while passing hidden BillingMesh API migration semantics and exact scope, and `X3 / opus 4.7max` passes all gates (`2313 <= 40000`). `X2` scoreably fails (`11 / 100`) after making no migration patch; `X6` is runtime `NOT-RUN` after no-summary timeout. This is the seventh compact single-session `X1 FAIL / X3 PASS` separator and the first compact real-repo API migration inverse after N53 tied on the smaller cache-ignored interface fixture | `N57 compact API migration operator-budget` |
| `62` | `N58` was added on `2026-04-24` as W38/E48 repeated-RHS MoM batch runtime analytical-oracle hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` passes the dual-physics regression, new MoM batch runtime oracle, exact scope, and runtime gates, but scoreably fails the visible operator-budget gate (`2530582 > 40000`). `X3 / opus 4.7max` passes all gates compactly (`2818 <= 40000`) and scores `100 / 100`. `X2` scoreably fails (`25 / 100`) after missing batch API/factor-reuse and tridiagonal markers; `X6` is runtime `NOT-RUN` after no-summary timeout. This is the eighth compact single-session `X1 FAIL / X3 PASS` separator and the first science/runtime inverse after N49 tied on compact scientific optimizer | `N58 MoM batch runtime analytical oracle` |
| `63` | `N59` was added on `2026-04-24` as W39/E49 real-repo performance-cache hardening; it is now superseded in canonical `/40` by N85. Historical N59 result: `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass hidden pricing semantics, batch runtime budget, exact patch scope, and evidence gates, so `binary tie remains`. Scored rubric separated role fit: `X1 PASS 90 / 100` with `336382` output bytes and cost `0`, while `X3 PASS 100 / 100` with `2653` output bytes and cost `10`. | `N59 superseded by N85` |
| `64` | `N60` was added on `2026-04-24` as W40/E50 UI visual-state reentry hardening; it is not merged into the old full-v2 denominator; `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass hidden UI state, ARIA/status, layout, raster-pixel, ledger, closure, test, and exact-scope gates, so `binary tie remains`. Scored rubric still favors X3: `X1 PASS 96 / 100` with `308696` output bytes, while `X3 PASS 100 / 100` with `3137` output bytes. `X2` scoreably fails (`10 / 100`) after making no patch and asking for next action; `X6` is runtime `NOT-RUN` after no-summary timeout. The first X3 launch hit usage limit before reset and is classified `NOT-RUN/runtime-route`, not a model failure | `N60 UI visual-state reentry` |
| `65` | `N62/N63` were added on `2026-04-25` as W41 frame-inversion diagnostics; they are not merged into `full-v2-hard` `/40`. `N62` puts N35-class staged interface requirements into a compact single-pass frame and both `X1` and `X3` pass, so N35/N36 should be read as staged re-entry/accountability separators rather than generic migration separators. `N63` puts N57-class compact API migration plus visible `40000` byte operator budget into staged wording: `X1` scoreably fails only the budget (`545831 > 40000`) after hidden API/scope pass, while `X3` passes all gates (`3190 <= 40000`). `X2` fails N62 by exact scope and N63 by budget; `X6` is runtime `NOT-RUN`; X5 quota probe timed out with no explicit quota/reset output | `W41 frame-inversion audit` |
| `66` | `N64` was added on `2026-04-25` as W42 security-depth review diagnostic for unresolved `L10`; it is not merged into `full-v2-hard` `/40`. The bundle requires nine exact vuln tuples and three false-positive exclusions. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass, so `binary tie remains` for ordinary security-depth review. `X2` scoreably fails by leaving the starter report unchanged. `X6` writes a locally verifier-passing report, but wrapperExitCode is `1` after Gemini capacity/tool-loop/AbortError, so it is runtime-caveat `NOT-RUN`, not clean pass | `N64 security depth review` |
| `67` | `N65` was added on `2026-04-25` as W43 visual-correctness review diagnostic for unresolved `L12`; it is not merged into `full-v2-hard` `/40`. The bundle requires eight exact UI visual defect tuples over DOM/CSS/state/screenshot-probe evidence and three false-positive exclusions. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass, so `binary tie remains` for ordinary visual-correctness review. `X2` scoreably fails by leaving the starter report unchanged. `X6` times out after `1800s` with no worker output or summary, so it is runtime `NOT-RUN` | `N65 visual correctness review` |
| `68` | `N66` was added on `2026-04-25` as W44 conflicting-evidence fact memo diagnostic for `L01`; it is not merged into `full-v2-hard` `/40`. The bundle requires source ranking, five conflict ledger rows, four confirmed facts, four non-claims, and bounded next action. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass, so `binary tie remains` for repo-understanding under conflicting sources. `X2` and `X6` both scoreably fail source-ranking/conflict/fact/non-claim gates | `N66 conflicting evidence memo` |
| `69` | `N67` was added on `2026-04-25` as W45 cross-phase integration-owner diagnostic; it is not merged into `full-v2-hard` `/40`. The staged bundle requires ledger, compatibility report, QA gate, and closure over a backend/frontend/QA cursor mismatch. `X1 / gpt-5.5` passes; `X3 / opus 4.7max` scoreably fails with wrapper `0` after missing pre-QA compatibility, QA-stop, repair/re-entry, and closure markers. `X2` scoreably fails the exact changed-path contract, and `X6` is runtime-caveat `NOT-RUN` because wrapperExitCode is `1` despite visible verifier failures | `N67 cross-phase integration owner` |
| `70` | `N68` was added on `2026-04-25` as W46 actual-screenshot visual review diagnostic; it is not merged into `full-v2-hard` `/40`. The bundle uses one PNG screenshot, eight seeded visual defects, coordinate windows, and false-positive traps. Both top rows fail the binary gate: `X1 / gpt-5.5` scores `70 / 100`, while `X3 / opus 4.7max` scores `80 / 100`. This is not a binary separator, but it gives X3 a scored edge for actual screenshot grounding. `X6` scoreably fails at `20 / 100`; `X2` is unsupported by the current visual runner; `X5` smoke timed out with no output | `N68 actual screenshot visual review` |
| `71` | `N69` was added on `2026-04-25` as W47 real-repo patch-quality scorecard diagnostic; it is not merged into `full-v2-hard` `/40`. The bundle has a hidden ledger implementation oracle plus runtime, exact required-path, auxiliary-churn, and output-cost scoring. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass hidden semantics, so `binary tie remains`. Rubric reads `X3 90 / 100` versus `X1 85 / 100`: X3 wins cost/compactness, while X1 has cleaner patch hygiene with no auxiliary cache churn. `X2` and `X6` both scoreably fail at `35 / 100`; X5 smoke timed out after `244s` with no output | `N69 patch-quality scorecard` |
| `72` | `N70` was added on `2026-04-25` as W48 multi-file entitlement event migration diagnostic; it is not merged into `full-v2-hard` `/40`. The bundle requires parser, engine, reporting, and ledger changes for hidden schema-v2 consumers, replacement, highest-sequence dedupe, hold/release state, summary counters, and runtime. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass hidden migration semantics, so `binary tie remains`. Rubric reads `X3 90 / 100` versus `X1 85 / 100`: X3 wins cost/compactness, while X1 has cleaner patch hygiene with no auxiliary cache churn. `X2` scoreably fails at `15 / 100`; `X6` is runtime-caveat `NOT-RUN` with wrapper `1` | `N70 entitlement migration scorecard` |
| `73` | `N71` was added on `2026-04-25` as W49 test-led rate-limit regression diagnostic; it is not merged into `full-v2-hard` `/40`. The bundle requires fixing hidden same-tenant different-user isolation and precise `retry_after`, plus adding a meaningful regression test. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass behavior and test-led gates, so `binary tie remains`. Rubric reads `X3 90 / 100` versus `X1 83 / 100`: X3 wins cost/compactness. `X2` and `X6` both scoreably fail at `15 / 100` | `N71 test-led rate-limit regression` |
| `74` | `N72` was added on `2026-04-25` as W50 caller-spanning API refactor diagnostic; it is not merged into `full-v2-hard` `/40`. The bundle requires schema-v2 `AccountRef` payloads, legacy `customer_id` compatibility, service/API/CLI/report propagation, payload immutability, exact five-file scope, and a refactor ledger. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass hidden caller contracts, so `binary tie remains`. Rubric reads `X3 90 / 100` versus `X1 83 / 100`: X3 wins cost/compactness. `X2` scoreably fails at `15 / 100`; `X6` is runtime `NOT-RUN` after a no-summary timeout, with local partial-run verifier failures | `N72 caller-spanning API refactor` |
| `75` | `N73` was added on `2026-04-25` as W51 DOM event runtime UI diagnostic; it is not merged into `full-v2-hard` `/40`. The verifier runs a Node DOM/event harness over filter clicks, keyboard dirty toggles, save behavior, exact scope, and payload immutability. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass and tie at `93 / 100`; `binary tie remains`. `X2` and `X6` both scoreably fail at `15 / 100` | `N73 DOM event runtime UI` |
| `76` | `N74` was added on `2026-04-25` as W52 DOM runtime output-budget diagnostic; it is not merged into `full-v2-hard` `/40`. The verifier repeats N73's Node DOM/event runtime harness and adds a visible `50000` byte operator-output budget. `X1 / gpt-5.5` scoreably fails only that budget after DOM runtime, exact scope, and ledger pass (`80 / 100`, `241980` bytes). `X3 / opus 4.7max` passes all gates (`100 / 100`, `2085` bytes). This is a compact inverse separator for runtime UI when output budget is first-class. `X2` and `X6` were not launched in W52 because W51 just calibrated the same DOM runtime base | `N74 DOM runtime output budget` |
| `77` | `N75` was added on `2026-04-25` as W53 persisted-state replay migration diagnostic; it is not merged into `full-v2-hard` `/40`. The bundle requires v1/v2 event normalization, source immutability, idempotent replay, checkpoint rollback, schema-v2 persist/load envelopes, exact six-path scope, and migration-ledger coverage. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass at `83 / 100`; `binary tie remains`. `X2` also passes at `75 / 100`, so this fixture shape is too easy as a top-pair semantic separator. `X6` is runtime `NOT-RUN` after `1800s` with no `summary.json` | `N75 persisted-state replay migration` |
| `78` | `N76` was added on `2026-04-25` as W54 staged persisted-state re-entry diagnostic; it is not merged into `full-v2-hard` `/40`. It repeats N75's runtime oracle but spreads source ledger, implementation, re-entry validation, and closeout across four fresh invocations. `X1 / gpt-5.5` passes (`85 / 100`). `X3 / opus 4.7max` scoreably fails (`15 / 100`) on missing `migrator.py` scope, schema version, persist envelope, and ledger/reentry/closeout contracts. `X2` scoreably fails exact staged scope (`70 / 100`). `X6` is runtime `NOT-RUN` after phase-2 timeout/capacity noise | `N76 staged persisted-state reentry` |
| `79` | `N77` was added on `2026-04-25` as W55 security capability runtime patch diagnostic; it is not merged into `full-v2-hard` `/40`. The verifier uses hidden runtime exploit attempts for HMAC capability tokens, tenant/user/resource binding, replay, expiry, redirect traps, audit redaction, exact scope, regression test, and ledger. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass, so `binary tie remains`. Rubric reads `X3 93 / 100` versus `X1 85 / 100`: X3 wins output cost, while X1 avoids auxiliary cache churn. `X2` scoreably fails at `15 / 100` after no patch; `X6` is runtime `NOT-RUN` after `2400s` with no `summary.json` | `N77 security capability runtime patch` |
| `80` | `N78` was added on `2026-04-25` as W56 staged security re-entry diagnostic; it is not merged into `full-v2-hard` `/40`. It repeats N77's hidden exploit oracle but stages threat ledger, implementation, exploit validation, re-entry state, and closeout across four fresh invocations. `X1 / gpt-5.5` passes (`85 / 100`). `X3 / opus 4.7max` scoreably fails (`23 / 100`) on a percent-encoded CRLF redirect trap plus staged ledger/validation/closeout contract gaps. `X2` scoreably fails (`45 / 100`) despite passing runtime exploit gates because exact scope and staged artifacts fail. `X6` is runtime `NOT-RUN` after `2400s` with no `summary.json` | `N78 staged security reentry` |
| `81` | `X4 / Claude China opus max` completed the admitted `full-v2-hard` closing run on `2026-04-26`: `32 / 40`, with `32 PASS`, `8 scoreable FAIL`, and `0 NOT-RUN`. Fails are `N25`, `N35`, `N36`, `N37`, `N39`, `N40`, `N43`, and `N57`. `N60` looked pending during polling but completed in the original batch as `PASS`; no retry result was admitted | `X4 full-v2-hard closing comparison` |
| `82` | `X2 / gpt-spark` filled all `21` former `full-v2-hard` `NOT-RUN` slots with `wrapperExitCode=0`: `7` new PASS and `14` new scoreable FAIL. Canonical `X2` is now closed at `12 / 40`. `X6 / flash-lite` filled `25` additional cells before Gemini quota exhaustion: current score is `13 / 40`, with `8` remaining `NOT-RUN` cells (`N56`, `N57`, `N35`, `N36`, `N04`, `S27`, `N37`, `S29`). A post-reset retry of normal cells hit `IneligibleTierError` on the current Gemini account; API-key route probe found no `GEMINI_API_KEY`, so these remain route/auth requeues rather than model failures | `X2/X6 full-v2-hard fill` |
| `83` | `N79` was added on `2026-04-28` as W57 staged UI/visual-state reentry diagnostic; it is not merged into `full-v2-hard` `/40`. It replaces brittle N38 with a four-phase source/state ledger, state/render implementation, layout/raster validation, and reentry closeout over the hidden N60 UI/raster oracle. `X1 / gpt-5.5` passes (`96 / 100`). `X3 / opus 4.7max` scoreably fails (`63 / 100`) after passing exact scope and phase-path discipline but missing visible blocked cue, focus return id, active descendant/accessibility, compact layout containment, raster overlay order, and ledger/closure markers. X4 and Gemini rows were not run by policy | `N79 staged UI visual-state reentry v2` |
| `84` | `N80` was added on `2026-04-28` as W58 calibrated screenshot-grounding diagnostic; it is not merged into `full-v2-hard` `/40`. It uses a deterministic `1600 x 1100` screenshot, ten seeded visual defects, `22 px` coordinate windows, semantic defect tuples, false-positive traps, and a score threshold. `X1 / gpt-5.5` passes (`82 / 100`, `8 / 10`, mean/max `2.855 / 7.071 px`). `X3 / opus 4.7max` scoreably fails (`63 / 100`, `7 / 10`, mean/max `8.067 / 17.117 px`) with one false-positive header ornament. X4 and Gemini rows were not run by policy | `N80 calibrated screenshot grounding` |
| `85` | `N83` was added on `2026-04-28` as W61 interface-refactor breakage diagnostic; it is not merged into `full-v2-hard` `/40`. It tests hidden batch-consumer behavior, duplicate-state preservation, rejected-request non-dispatch, structured-report compatibility, legacy interface removal, exact ten-path scope, visible regression markers, and migration ledger. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass with wrapper `0`, so `binary tie remains`. The v2 runner now treats top-level `.pytest_cache/` as auxiliary generated cache | `N83 interface-refactor breakage hunt` |
| `86` | `N86` was added on `2026-04-28` as W65 real interface downstream migration diagnostic; it is not merged into `full-v2-hard` `/40`. It removes the N57 operator-output budget and adds a hidden downstream public-app contract over root package exports, dataclass serialization, denied-without-publish, timeout retryability, duplicate non-republish, structured reporting, source-bound ledgers, review response, closeout, and exact scope. `X1 / gpt-5.5` passes. `X3 / opus 4.7max` scoreably fails only exact scope after passing hidden interface/downstream semantics: missing `candidate/workspace/src/billingmesh/api.py` | `N86 real interface downstream migration` |
| `87` | `N87` was added on `2026-04-28` as W66 performance-review gate diagnostic; it is not merged into `full-v2-hard` `/40`. It is a read-only review gate over warm-cache benchmark contamination, cache-key context loss, global cache lifetime growth, approval-gate incompleteness, false-positive restraint, response decisions, and exact `REVISE` gate. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass with wrapper `0`, so `binary tie remains`; X3 is much more compact (`2466` bytes versus `154170`) but not a binary winner | `N87 performance review gate` |
| `88` | `N88` was added on `2026-04-28` as W67 UX runtime event-policy simulator diagnostic; it is not merged into `full-v2-hard` `/40`. It replaces term-matched UX JSON anchors with hidden event-policy traces for stale remote source, missing owner, missing regression proof, combined-failure priority, auditor export, follow-up diff, ready-state publishing, breakpoint ordering, and re-entry persistence. `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass with wrapper `0`, so `binary tie remains`; X3 is much more compact (`2758` bytes versus `151375`) but no output budget is part of this UX design contract | `N88 UX runtime event-policy simulator` |
| `89` | `N89` was added on `2026-04-28` as W68 security runtime witness review diagnostic; it is not merged into `full-v2-hard` `/40`. It keeps a review-only `candidate/review-report.json` surface and adds verifier-owned executable witnesses, exact structured `witnessMatrix` rows, protected review-target hashes, and exact false-positive cardinality. Admitted v3 result: `X1 / gpt-5.5` and `X3 / opus 4.7max` both pass with wrapper `0`, so `binary tie remains`; X3 is much more compact (`1951` bytes versus `158078`) but no output budget is part of this security-review contract | `N89 security runtime witness review` |

## Source

| Source | Role |
|---|---|
| `full-v2-hard-results-current.md` | current canonical hardened `/40` surface and slot matrix |
| `x1-x3-steady-state-core-results-2026-04-17.md` | legacy admitted ranking surface for the old upgraded-pack architecture |
| `x1-x3-full-registry-results-2026-04-17.md` | legacy widest execution-backed registry surface for the old upgraded-pack architecture |
| `v2-full-s01-s33-n01-n07-results-2026-04-18.md` | deprecated pre-v3 expanded full-v2 baseline for `X1`, `X2`, `X3`, `X4`, `X5`, and `X6`; superseded by `full-v2-hard-results-current.md` for classification |
| `v2-extra-lane-n08-n10-results-2026-04-20.md` | reference extra-lane result surface for `E1 worker.long-autonomous` |
| `v2-core12-tie-hardened-results-2026-04-20.md` | hardened weak-separator targeted result surface for `X1`, `X3`, and `X5` |
| `v2-top-pair-separators-n11-n13-results-2026-04-20.md` | diagnostic `E2` result surface for `X1` and `X3` |
| `v2-top-pair-rubric-e3-results-2026-04-20.md` | diagnostic `E3` rubric result over fresh 2026-04-21 `N11..N13` outputs |
| `role-fit-scorecard-v1-2026-04-22.md` | lane-fit routing read: X1/X3 role recommendations plus X2/X5/X6 calibration policy |
| `v2-full-s01-s33-results-2026-04-18.md` | earlier same-day `S01..S33` checkpoint, now superseded as the main live v2 read |
| `../Evidence/x1-x2-x3-x4-x5-x6-full-v2-s01-s33-n01-n07-2026-04-18.md` | expanded six-row full-v2 evidence and caveat source |
| `../Evidence/x1-x2-x3-x5-x6-v2-n08-n10-worker-long-autonomous-2026-04-20.md` | extra-lane `N08..N10` evidence and deferred `X4` route source |
| `../Evidence/x1-x3-x5-core12-tie-hardened-2026-04-20.md` | hardened weak-separator evidence and timeout diagnostics |
| `../Evidence/x5-core12-timeout-closure-2026-04-20.md` | timeout closure evidence for `X5` hardened subset |
| `../Evidence/x1-x3-top-pair-separators-n11-n13-2026-04-20.md` | diagnostic `E2` execution evidence and hardening delta |
| `../Evidence/x1-x3-top-pair-rubric-e3-2026-04-20.md` | diagnostic `E3` rubric evidence |
| `../Evidence/x1-control-plane-override-rerun-s16-s19-s20-2026-04-20.md` | targeted `X1` rerun evidence for `S16`, `S19`, and `S20` |
| `../Evidence/separator-audit-2026-04-21.md` | factual audit of answer-leakage, verifier strictness, and separation potential across all 43 scenarios; motivates the N06 tuple-exact hardening |
| `../Evidence/x1-mainline-hardening-no-new-failures-2026-04-21.md` | contains the admitted N06, wave-2 review, wave-3 S06, wave-4 S22, and N14..N83 hardening sections |
| `../Evidence/n16-long-horizon-rubric-2026-04-22.json` | machine-readable N16 scored-rubric output for admitted `X1` and `X3` runs |
| `../Evidence/n17-owner-routing-rubric-2026-04-22.json` | machine-readable N17 owner-orchestration scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` runs |
| `../Evidence/n18-scientist-constraints-rubric-2026-04-22.json` | machine-readable N18 scientist/constraints scored-rubric output for admitted `X1`, `X2`, `X3`, partial-route `X6`, and timeout `X5` runs |
| `../Evidence/n19-systems-toolchain-rubric-2026-04-22.json` | machine-readable N19 systems/toolchain scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` runs |
| `../Evidence/n20-ui-interaction-rubric-2026-04-22.json` | machine-readable N20 UI interaction scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` runs |
| `../Evidence/n21-visual-raster-rubric-2026-04-22.json` | machine-readable N21 visual-raster scored-rubric output for admitted `X1`, `X2`, `X3`, `X5`, and `X6` launch attempts |
| `../Evidence/n22-numerical-stability-rubric-2026-04-22.json` | machine-readable N22 numerical-stability scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` runs |
| `../Evidence/n23-owner-recovery-rubric-2026-04-22.json` | machine-readable N23 owner-recovery scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` runs |
| `../Evidence/n24-toolchain-repeat-rubric-2026-04-22.json` | machine-readable N24 systems/toolchain repeat scored-rubric output for admitted `X1`, `X2`, `X3`, `X5`, and `X6` runs |
| `../Evidence/n25-ui-dirty-repeat-rubric-2026-04-22.json` | machine-readable N25 UI dirty-state repeat scored-rubric output for admitted `X1`, `X2`, `X3`, `X5`, and `X6` runs |
| `../Evidence/n26-owner-wave-rubric-2026-04-22.json` | machine-readable N26 owner recovery repeat scored-rubric output for admitted `X1`, `X2`, `X3`, `X5`, and `X6` runs |
| `../Evidence/n27-release-train-rubric-2026-04-22.json` | machine-readable N27 long-horizon release-train scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` runs; `X5` stayed smoke-gated `REQUEUE` |
| `../Evidence/n28-incident-repair-rubric-2026-04-22.json` | machine-readable N28 incident-driven integration repair scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` runs; `X5` stayed smoke-gated `REQUEUE` |
| `../Evidence/n29-ownership-budget-rubric-2026-04-23.json` | machine-readable N29 ownership-budget incident repair scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` launch roots; `X5` stayed smoke-gated `REQUEUE` |
| `../Evidence/n30-staged-delivery-rubric-2026-04-23.json` | machine-readable N30 staged delivery re-entry scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` launch roots; `X5` stayed smoke-gated `REQUEUE` |
| `../Evidence/n31-mom-cylinder-rubric-2026-04-23.json` | machine-readable N31 Method of Moments PEC-cylinder analytical-oracle scored-rubric output for admitted `X1` and `X3` runs |
| `../Evidence/n32-dual-physics-rubric-2026-04-23.json` | machine-readable N32 dual-physics analytical-oracle scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` launch roots; `X5` stayed smoke-gated `REQUEUE` |
| `../Evidence/n33-interface-refactor-rubric-2026-04-23.json` | machine-readable N33 interface-refactor scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` launch roots; `X5` stayed route-gated `REQUEUE` |
| `../Evidence/n34-science-optimizer-rubric-2026-04-23.json` | machine-readable N34 high-load science optimizer scored-rubric output for admitted `X1`, `X2`, and `X3`; Gemini rows stayed route caveats |
| `../Evidence/n35-staged-interface-rubric-2026-04-23.json` | machine-readable N35 staged interface-migration re-entry scored-rubric output for admitted `X1`, `X2`, and `X3`; `X5` and `X6` are runtime-route failures, not model-quality failures |
| `../Evidence/n36-staged-api-rubric-2026-04-23.json` | machine-readable N36 real-repo staged API migration scored-rubric output for admitted `X1`, `X2`, and `X3`; `X6` is runtime no-summary and `X5` stayed smoke-gated |
| `../Evidence/n37-staged-review-rubric-2026-04-23.json` | machine-readable N37 staged adversarial review-gate scored-rubric output for admitted `X1`, `X2`, `X3`, `X5`, and `X6`; X3 is a scoreable top-pair fail, X5/X6 are runtime-route caveats |
| `../Evidence/n38-ui-visual-state-rubric-2026-04-23.json` | machine-readable N38 staged UI/visual/state scored-rubric output for admitted `X1`, `X2`, `X3`, `X5`, and `X6` launch roots; X3 is repeated runtime no-summary after three attempts, X5/X6 are runtime-route caveats |
| `../Evidence/n39-staged-toolchain-rubric-2026-04-23.json` | machine-readable N39 staged systems/toolchain re-entry scored-rubric output for admitted `X1`, `X2`, `X3`, `X5`, and `X6` launch roots; bounded-scope rerun makes it a scoreable X1-over-X3 staged systems/toolchain separator |
| `../Evidence/n40-staged-owner-rubric-2026-04-23.json` | machine-readable N40 staged owner-recovery re-entry scored-rubric output for admitted `X1`, `X2`, `X3`, `X5`, and `X6` launch roots; X1 is the only pass and X3 is a scoreable staged-owner fail |
| `../Evidence/n41-staged-incident-budget-rubric-2026-04-23.json` | machine-readable N41 staged incident-budget re-entry scored-rubric output for admitted `X1`, `X2`, `X3`, `X5`, and `X6` launch roots; X1 is the only pass among scoreable rows and X3 is a staged incident-budget fail |
| `../Evidence/n45-ownership-report-rubric-2026-04-24.json` | machine-readable N45 ownership-budget immutable report-consumer scored-rubric output for admitted `X1` and `X3` launch roots; both pass and X3 wins only by output-cost points |
| `../Evidence/n46-operator-budget-rubric-2026-04-24.json` | machine-readable N46 operator-budget compact-hotfix scored-rubric output for admitted `X1` and `X3` launch roots; X1 scoreably fails the visible output budget while preserving hidden repair semantics, and X3 passes all gates compactly |
| `../Evidence/n47-ui-operator-budget-rubric-2026-04-24.json` | machine-readable N47 UI compact operator-budget scored-rubric output for admitted `X1` and `X3` launch roots; X1 scoreably fails the visible output budget while preserving hidden UI dirty-state semantics, and X3 passes all gates compactly |
| `../Evidence/n48-visual-operator-budget-rubric-2026-04-24.json` | machine-readable N48 visual raster compact operator-budget scored-rubric output for admitted `X1` and `X3` launch roots; X1 scoreably fails the visible output budget while preserving exact visual semantics, and X3 passes all gates compactly |
| `../Evidence/n49-science-operator-budget-rubric-2026-04-24.json` | machine-readable N49 scientific compact operator-budget scored-rubric output for admitted `X1` and `X3` launch roots; both pass full computational-physics semantics, exact scope, and visible output budget; X3 wins only by runtime rubric points |
| `../Evidence/n50-systems-operator-budget-rubric-2026-04-24.json` | machine-readable N50 systems compact operator-budget scored-rubric output for admitted `X1` and `X3` launch roots; both pass hidden stagegate semantics, protected test hash, exact scope, and visible output budget; X3 wins only by elapsed time |
| `../Evidence/n51-systems-turnaround-budget-rubric-2026-04-24.json` | machine-readable N51 systems turnaround-budget scored-rubric output for admitted `X1` and `X3` launch roots; both fail scoreably under combined semantics, output budget, and turnaround constraints |
| `../Evidence/n52-interface-refactor-operator-budget-rubric-2026-04-24.json` | machine-readable N52 interface-refactor compact operator-budget scored-rubric output for admitted `X1` and `X3` launch roots; both fail scoreably for different reasons |
| `../Evidence/n53-interface-refactor-cache-ignored-rubric-2026-04-24.json` | machine-readable N53 interface-refactor cache-ignored operator-budget scored-rubric output for admitted `X1` and `X3` launch roots; both pass after top-level `.pytest_cache/**` is explicitly ignored as generated test cache |
| `../Evidence/n54-release-train-operator-budget-rubric-2026-04-24.json` | machine-readable N54 release-train compact operator-budget scored-rubric output for admitted `X1` and `X3` launch roots; X1 fails only the visible output budget while X3 passes all gates compactly |
| `../Evidence/n55-incident-operator-budget-rubric-2026-04-24.json` | machine-readable N55 incident compact operator-budget scored-rubric output for admitted `X1` and `X3` launch roots; X1 fails only the visible output budget while X3 passes all gates compactly |
| `../Evidence/n56-owner-operator-budget-rubric-2026-04-24.json` | machine-readable N56 compact owner-recovery operator-budget scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` launch roots; X1 fails only the visible output budget while X3 passes all gates compactly; X2 is scoreable lower calibration fail and X6 is runtime no-summary |
| `../Evidence/n57-compact-api-migration-rubric-2026-04-24.json` | machine-readable N57 compact real-repo API migration operator-budget scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` launch roots; X1 fails only the visible output budget while X3 passes all hidden API migration, scope, and budget gates compactly; X2 is scoreable lower calibration fail and X6 is runtime no-summary |
| `../Evidence/n58-mom-batch-runtime-rubric-2026-04-24.json` | machine-readable N58 repeated-RHS MoM batch runtime scored-rubric output for admitted `X1`, `X2`, `X3`, and `X6` launch roots; X1 passes physics/runtime/scope but fails only the visible output budget, X3 passes all gates compactly, X2 is scoreable lower calibration fail, and X6 is runtime no-summary |
| `../Evidence/n59-perf-cache-rubric-2026-04-24.json` | historical N59 real-repo performance-cache scored-rubric output; superseded in canonical `/40` by `../Evidence/n85-performance-runtime-rubric-2026-04-28.json` |
| `../Evidence/n85-performance-runtime-rubric-2026-04-28.json` | machine-readable W63 performance runtime replacement evidence; X1 fails only hard output budget after hidden runtime/scope pass, X3 passes all gates, X2 fails scoreably, X6 is route/auth `NOT-RUN` |
| `../Evidence/n60-ui-reentry-rubric-2026-04-24.json` | machine-readable N60 UI visual-state reentry scored-rubric output for admitted `X1`, post-reset `X3`, `X2`, and `X6` launch roots; X1 and X3 both pass binary gates, X3 wins cost/compactness (`100` versus `96`), X2 fails scoreably, and X6 is runtime no-summary |
| `../Evidence/n61-visual-pixel-localization-rubric-2026-04-25.json` | machine-readable N61 visual pixel-localization diagnostic evidence; post-fix X1/X3/X6 all fail binary gate, X1 wins secondary score `65.1` versus `50.0` versus `40.0`, and official X5 is runtime NOT-RUN after timeout |
| `../Evidence/n62-n63-frame-inversion-rubric-2026-04-25.json` | machine-readable W41 frame-inversion diagnostic evidence; N62 ties X1/X3 under compact frame, N63 repeats X1 FAIL / X3 PASS under staged wording, and X2/X6/X5 remain calibration/runtime context |
| `../Evidence/n64-security-depth-rubric-2026-04-25.json` | machine-readable W42 security-depth diagnostic evidence; X1/X3 both pass exact nine-finding gate, X2 fails scoreably, and X6 is runtime caveat despite local verifier pass |
| `../Evidence/n65-visual-correctness-rubric-2026-04-25.json` | machine-readable W43 visual-correctness diagnostic evidence; X1/X3 both pass exact eight-finding gate, X2 fails scoreably, and X6 is runtime timeout |
| `../Evidence/n66-conflicting-evidence-rubric-2026-04-25.json` | machine-readable W44 conflicting-evidence diagnostic evidence; X1/X3 both pass exact source-ranking/conflict-ledger gate, while X2/X6 fail scoreably |
| `../Evidence/n67-cross-phase-integration-rubric-2026-04-25.json` | machine-readable W45 cross-phase integration-owner diagnostic evidence; X1 passes, X3 fails scoreably, X2 fails scoreably, and X6 is runtime-caveat NOT-RUN |
| `../Evidence/n68-actual-screenshot-visual-review-rubric-2026-04-25.json` | machine-readable W46 actual-screenshot visual grounding evidence; both top rows fail, X3 scores higher, X6 fails scoreably, X5 route remains unhealthy |
| `../Evidence/n69-patch-quality-rubric-2026-04-25.json` | machine-readable W47 real-repo patch-quality scorecard evidence; X1 and X3 both pass hidden semantics, X3 wins cost score, X1 wins patch-hygiene score, and X2/X6 fail scoreably |
| `../Evidence/n70-entitlement-migration-rubric-2026-04-25.json` | machine-readable W48 multi-file entitlement migration scorecard evidence; X1 and X3 both pass hidden schema-v2 consumers, X3 wins cost score, X1 wins patch-hygiene score, X2 fails scoreably, and X6 is runtime-caveat NOT-RUN |
| `../Evidence/n71-test-led-rubric-2026-04-25.json` | machine-readable W49 test-led regression scorecard evidence; X1 and X3 both pass behavior and regression-test gates, X3 wins cost score, and X2/X6 fail scoreably |
| `../Evidence/n72-caller-refactor-rubric-2026-04-25.json` | machine-readable W50 caller-spanning API refactor evidence; X1 and X3 both pass hidden API/service/CLI/report callers, X3 wins cost score, X2 fails scoreably, and X6 is runtime no-summary |
| `../Evidence/n73-dom-runtime-rubric-2026-04-25.json` | machine-readable W51 DOM event runtime UI evidence; X1 and X3 both pass runtime filter/keyboard/save behavior and tie at `93 / 100`, while X2/X6 fail scoreably |
| `../Evidence/n74-dom-runtime-budget-rubric-2026-04-25.json` | machine-readable W52 DOM runtime output-budget evidence; X1 passes runtime semantics but fails visible output budget, while X3 passes all gates |
| `../Evidence/n75-persisted-state-rubric-2026-04-25.json` | machine-readable W53 persisted-state replay migration evidence; X1, X3, and X2 pass hidden semantics, while X6 is runtime no-summary |
| `../Evidence/n76-staged-persisted-state-rubric-2026-04-25.json` | machine-readable W54 staged persisted-state reentry evidence; X1 passes, X3/X2 fail scoreably, and X6 is runtime no-summary |
| `../Evidence/n77-security-capability-rubric-2026-04-25.json` | machine-readable W55 security capability runtime patch evidence |
| `../Evidence/n78-staged-security-rubric-2026-04-25.json` | machine-readable W56 staged security re-entry evidence |
| `../Evidence/n79-staged-ui-reentry-rubric-2026-04-28.json` | machine-readable W57 staged UI visual-state reentry evidence |
| `../Evidence/n80-screenshot-grounding-rubric-2026-04-28.json` | machine-readable W58 calibrated screenshot-grounding evidence |
| `../Evidence/n81-evidence-action-rubric-2026-04-28.json` | machine-readable W59 evidence-conflict action-plan evidence; X1 and X3 both pass `24 / 24`, so `binary tie remains` |
| `../Evidence/n82-ux-state-rubric-2026-04-28.json` | machine-readable W60 UX runtime-state evidence; X1 and X3 both pass `27 / 27`, so `binary tie remains` |
| `../Evidence/n83-interface-refactor-breakage-rubric-2026-04-28.json` | machine-readable W61 interface-refactor breakage evidence; X1 and X3 both pass hidden batch-consumer and structured-report runtime gates, so `binary tie remains` |
| `../Evidence/n86-interface-downstream-rubric-2026-04-28.json` | machine-readable W65 real interface downstream migration evidence; X1 passes, while X3 passes hidden downstream semantics but scoreably fails exact migration-surface scope |
| `../Evidence/n87-performance-review-gate-rubric-2026-04-28.json` | machine-readable W66 performance-review gate evidence; X1 and X3 both pass, so `binary tie remains` |
| `../Evidence/n88-ux-runtime-policy-rubric-2026-04-28.json` | machine-readable W67 UX runtime event-policy evidence; X1 and X3 both pass, so `binary tie remains` |
| `../Evidence/n89-security-runtime-witness-rubric-2026-04-28.json` | machine-readable W68 security runtime witness review evidence; X1 and X3 both pass, so `binary tie remains` |
| `../Evidence/x4-full-v2-hard-2026-04-26.json` | machine-readable X4 full-v2-hard closing comparison evidence |
| `../Evidence/x2-x6-fill-full-v2-hard-2026-04-26.json` | machine-readable X2/X6 full-v2-hard fill evidence |

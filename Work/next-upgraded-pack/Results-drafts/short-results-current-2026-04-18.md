Date: 2026-04-22
Owner: `$lead`
Status: `PASS`

## Result

This is the current compact operator read for the live benchmark state.

The old upgraded-pack tables remain the last full execution checkpoint for the legacy
upgraded-pack architecture only.
The expanded full `S01..S33 + N01..N07` surface below is now treated as a `pre-v3` ceiling-effect
baseline, not as final classification evidence. V3 hardening replaces stale lines in this same live
surface as hardened scenario evidence is admitted.

`Scenarios-v2` is quota-aware across the expanded full `S01..S33 + N01..N07` surface for
`X1`, `X2`, `X3`, `X4`, `X5`, and `X6`. Explicit provider quota / usage-limit failures are
`NOT-RUN` / `REQUEUE`, not scoreable `FAIL`. `X5` is no longer quota-pending; the former
`S12` timeout reran into a scoreable verifier-level `FAIL`.

`worker.long-autonomous` is now materialized as reference extra lane `E1` with `N08..N10`.
It is scored separately from the core `12` routing lanes. `X4` is `NOT-RUN` on this extra slice
because the required secret-backed Claude route returned provider `502`.

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

| ID | Label |
|---|---|
| `X1` | `gpt-5.4` |
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

| `#` | Current rows note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | pre-v3 expanded full-v2 score was `39 / 40`; treat as ceiling-effect baseline until hardened reruns replace it |
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
| `2` | `X4` current read is valid only on the repo-canonical secret-backed Claude path; earlier same-day non-secret and broken-path attempts are not part of the admitted table | `Claude China` |
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

## Source

| Source | Role |
|---|---|
| `x1-x3-steady-state-core-results-2026-04-17.md` | legacy admitted ranking surface for the old upgraded-pack architecture |
| `x1-x3-full-registry-results-2026-04-17.md` | legacy widest execution-backed registry surface for the old upgraded-pack architecture |
| `v2-full-s01-s33-n01-n07-results-2026-04-18.md` | full current expanded v2 result surface for `X1`, `X2`, `X3`, `X4`, `X5`, and `X6` |
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
| `../Evidence/x1-mainline-hardening-no-new-failures-2026-04-21.md` | contains the admitted N06, wave-2 review, wave-3 S06, wave-4 S22, Option (c) N14, N15 stateful gauntlet, and N16 long-horizon rubric sections |
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

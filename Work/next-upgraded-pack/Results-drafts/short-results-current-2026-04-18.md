Date: 2026-04-21
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
| `v2-full-s01-s33-results-2026-04-18.md` | earlier same-day `S01..S33` checkpoint, now superseded as the main live v2 read |
| `../Evidence/x1-x2-x3-x4-x5-x6-full-v2-s01-s33-n01-n07-2026-04-18.md` | expanded six-row full-v2 evidence and caveat source |
| `../Evidence/x1-x2-x3-x5-x6-v2-n08-n10-worker-long-autonomous-2026-04-20.md` | extra-lane `N08..N10` evidence and deferred `X4` route source |
| `../Evidence/x1-x3-x5-core12-tie-hardened-2026-04-20.md` | hardened weak-separator evidence and timeout diagnostics |
| `../Evidence/x5-core12-timeout-closure-2026-04-20.md` | timeout closure evidence for `X5` hardened subset |
| `../Evidence/x1-x3-top-pair-separators-n11-n13-2026-04-20.md` | diagnostic `E2` execution evidence and hardening delta |
| `../Evidence/x1-x3-top-pair-rubric-e3-2026-04-20.md` | diagnostic `E3` rubric evidence |
| `../Evidence/x1-control-plane-override-rerun-s16-s19-s20-2026-04-20.md` | targeted `X1` rerun evidence for `S16`, `S19`, and `S20` |

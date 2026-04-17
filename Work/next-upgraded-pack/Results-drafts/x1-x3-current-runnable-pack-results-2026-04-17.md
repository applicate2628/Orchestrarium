Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file records the full execution-backed result surface for the **current runnable mutable
pack** across `X1`, `X2`, and `X3`.

This is **not** the full `T01..T33` registry and **not** the final steady-state core pack. It is
the set of benchmark tests that are already concrete, locally validated, and fully executed across
the active cohort.

## Scope

| Field | Value |
|---|---|
| active rows | `X1`, `X2`, `X3` |
| result surface | current runnable mutable pack |
| total runnable tests in this surface | `15` |
| included tests | `T08`, `T09`, `T10`, `T22`, `T23`, `T24`, `T25`, `T26`, `T27`, `T28`, `T29`, `T30`, `T31`, `T32`, `T33` |
| excluded registry/core tests | `T01..T07`, `T11..T21` |
| primary emphasis | worker-side implementation, toolchain ownership, long-horizon continuity, harder non-browser UI/static probes |

## Coverage summary

| Row | Tests passed | Caveats | Read |
|---|---:|---|---|
| `X1` | `15 / 15` | none material | cleanest current runnable-pack row |
| `X2` | `15 / 15` | `T29` carries a toolchain-discipline penalty | admitted green, but not as clean as `X1` or `X3` |
| `X3` | `15 / 15` | none material | full green across the entire current runnable pack |

## Per-test result table

| `#` | Test | `X1` | `X2` | `X3` | Notes |
|---|---|---|---|---|---|
| `1` | `T08` | `PASS` | `PASS` | `PASS` | provider-local owner seam stable across all three rows |
| `2` | `T09` | `PASS` | `PASS` | `PASS` | root-cause plus owner-debug seam stable across all three rows |
| `3` | `T10` | `PASS` | `PASS` | `PASS` | stale-context rejection stable across all three rows |
| `4` | `T22` | `PASS` | `PASS` | `PASS` | build-owner continuity stable across all three rows |
| `5` | `T23` | `PASS` | `PASS` | `PASS` | path-recall continuity stable across all three rows |
| `6` | `T24` | `PASS` | `PASS` | `PASS` | multi-step worker persistence stable across all three rows |
| `7` | `T25` | `PASS` | `PASS` | `PASS` | messy worker ownership passes across all three rows |
| `8` | `T26` | `PASS` | `PASS` | `PASS` | toolchain-owner ambiguity passes across all three rows |
| `9` | `T27` | `PASS` | `PASS` | `PASS` | `X2` and `X3` use a narrower one-file accepted repair; verifier remained green |
| `10` | `T28` | `PASS` | `PASS` | `PASS` | reviewer-to-worker transition passes across all three rows |
| `11` | `T29` | `PASS` | `PASS*` | `PASS` | `X2` widened into `repo/apps/service-app/src/runToolchainTask.js`, so the row carries a toolchain-discipline penalty |
| `12` | `T30` | `PASS` | `PASS` | `PASS` | wrong-file-attraction static UI probe stays clean across all three rows |
| `13` | `T31` | `PASS` | `PASS` | `PASS` | fallback noisy-evidence filter passes cleanly across all three rows |
| `14` | `T32` | `PASS` | `PASS` | `PASS` | constrained multi-step patching passes cleanly across all three rows |
| `15` | `T33` | `PASS` | `PASS` | `PASS` | decorative consistency probe passes cleanly across all three rows |

## Row-level interpretation

| Row | Current read |
|---|---|
| `X1` | strongest current runnable-pack row: all `15` tests pass with no material ownership or toolchain caveat |
| `X2` | admitted green across all `15` tests, but `T29` remains materially less disciplined than `X1` and `X3` |
| `X3` | admitted green across all `15` tests with no material caveat; very close to `X1` on the current runnable surface |

## Current runnable-pack ordering

| Rank | Row | Why |
|---|---|---|
| `1` | `X1` | clean full pass with no material penalty on the current runnable surface |
| `2` | `X3` | clean full pass, but `X1` remains slightly cleaner on continuity details already observed in earlier batches |
| `3` | `X2` | full pass count matches `X1` and `X3`, but the `T29` widening penalty keeps it below them |

## Evidence basis

| Row | Batch 1 | Batch 2 | Batch 3 |
|---|---|---|---|
| `X1` | `Evidence/x1-worker-heavy-first-batch-2026-04-17.md` | `Evidence/x1-worker-followup-second-batch-2026-04-17.md` | `Evidence/x1-new-design-third-batch-2026-04-17.md` |
| `X2` | `Evidence/x2-worker-heavy-first-batch-2026-04-17.md` | `Evidence/x2-worker-followup-second-batch-2026-04-17.md` | `Evidence/x2-new-design-third-batch-2026-04-17.md` |
| `X3` | `Evidence/x3-worker-heavy-first-batch-2026-04-17.md` | `Evidence/x3-worker-followup-second-batch-2026-04-17.md` | `Evidence/x3-new-design-third-batch-2026-04-17.md` |

## Boundary note

These results are sufficient to say that the **current runnable mutable pack** is complete for
`X1..X3`.

They are not yet sufficient to claim a full next-pack ranking across every intended steady-state
core anchor, because `T01`, `T03`, `T05`, `T07`, `T12`, `T15`, `T18`, `T19`, and `T21` are still
outside the current runnable execution surface.

## Next step

Decide whether to freeze this worker-heavy runnable checkpoint as the current admitted mutable
surface, or backfill the remaining non-runnable core anchors before the next ranking refresh.

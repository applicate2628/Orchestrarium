Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file records the full execution-backed registry surface for `X1`, `X2`, and `X3`.

Unlike the smaller steady-state core surface, this file covers the entire current runnable test
registry:

- `T01..T33`

## Scope

| Field | Value |
|---|---|
| active rows | `X1`, `X2`, `X3` |
| result surface | full execution-backed registry |
| total registry tests | `33` |
| completed rows | `X1`, `X2`, `X3` |
| admitted caveat carried forward | `X2` still carries the `T29` toolchain-discipline penalty |

## Coverage summary

| Row | Completed registry tests | Status | Caveats | Read |
|---|---:|---|---|---|
| `X1` | `33 / 33` | `COMPLETE` | none material | cleanest full-registry row |
| `X2` | `33 / 33` | `COMPLETE` | `T29` still carries the earlier toolchain-discipline penalty | full registry green, but not as clean as `X1` or `X3` |
| `X3` | `33 / 33` | `COMPLETE` | none material | full registry green; closest full-registry row to `X1` |

## Per-test result table

| `#` | Test | `X1` | `X2` | `X3` | Notes |
|---|---|---|---|---|---|
| `1` | `T01` | `PASS` | `PASS` | `PASS` | bounded repo-understanding anchor is green across all three rows |
| `2` | `T02` | `PASS` | `PASS` | `PASS` | source-of-truth reconciliation is green across all three rows |
| `3` | `T03` | `PASS` | `PASS` | `PASS` | ADR plus risk reasoning anchor is green across all three rows |
| `4` | `T04` | `PASS` | `PASS` | `PASS` | phased planning structure is green across all three rows |
| `5` | `T05` | `PASS` | `PASS` | `PASS` | findings-only review anchor is green across all three rows |
| `6` | `T06` | `PASS` | `PASS` | `PASS` | security reasoning memo is green across all three rows |
| `7` | `T07` | `PASS` | `PASS` | `PASS` | systems and performance memo anchor is green across all three rows |
| `8` | `T08` | `PASS` | `PASS` | `PASS` | provider-local owner seam is green across all three rows |
| `9` | `T09` | `PASS` | `PASS` | `PASS` | root-cause and owner-debug seam is green across all three rows |
| `10` | `T10` | `PASS` | `PASS` | `PASS` | resume and long-horizon hybrid anchor is green across all three rows |
| `11` | `T11` | `PASS` | `PASS` | `PASS` | roadmap-priority triage is green across all three rows |
| `12` | `T12` | `PASS` | `PASS` | `PASS` | product brief grounding anchor is green across all three rows |
| `13` | `T13` | `PASS` | `PASS` | `PASS` | reliability and rollout-safety memo is green across all three rows |
| `14` | `T14` | `PASS` | `PASS` | `PASS` | proof-framing memo is green across all three rows |
| `15` | `T15` | `PASS` | `PASS` | `PASS` | build-break diagnosis anchor is green across all three rows |
| `16` | `T16` | `PASS` | `PASS` | `PASS` | backend owner-implementation stays green across all three rows |
| `17` | `T17` | `PASS` | `PASS` | `PASS` | static UI structure patch stays green across all three rows |
| `18` | `T18` | `PASS` | `PASS` | `PASS` | static UI evidence triage anchor is green across all three rows |
| `19` | `T19` | `PASS` | `PASS` | `PASS` | accessibility and UX findings anchor is green across all three rows |
| `20` | `T20` | `PASS` | `PASS` | `PASS` | visual-review findings stay green across all three rows |
| `21` | `T21` | `PASS` | `PASS` | `PASS` | worker path-discovery anchor is green across all three rows |
| `22` | `T22` | `PASS` | `PASS` | `PASS` | build-owner continuity stays green across all three rows |
| `23` | `T23` | `PASS` | `PASS` | `PASS` | path-recall continuity stays green across all three rows |
| `24` | `T24` | `PASS` | `PASS` | `PASS` | multi-step persistence stays green across all three rows |
| `25` | `T25` | `PASS` | `PASS` | `PASS` | messy worker ownership stays green across all three rows |
| `26` | `T26` | `PASS` | `PASS` | `PASS` | toolchain-owner ambiguity stays green across all three rows |
| `27` | `T27` | `PASS` | `PASS` | `PASS` | late-session recall stays green across all three rows |
| `28` | `T28` | `PASS` | `PASS` | `PASS` | reviewer-to-worker transition stays green across all three rows |
| `29` | `T29` | `PASS` | `PASS*` | `PASS` | `X2` widened into `src/runToolchainTask.js`, so the row still carries a toolchain-discipline penalty |
| `30` | `T30` | `PASS` | `PASS` | `PASS` | stronger static UI probe stays green across all three rows |
| `31` | `T31` | `PASS` | `PASS` | `PASS` | fallback noisy-evidence filter stays green across all three rows |
| `32` | `T32` | `PASS` | `PASS` | `PASS` | constrained multi-step patching stays green across all three rows |
| `33` | `T33` | `PASS` | `PASS` | `PASS` | decorative consistency stays green across all three rows |

## Current ordering

| Rank | Row | Why |
|---|---|---|
| `1` | `X1` | full registry complete with no material caveat and the cleanest admitted read overall |
| `2` | `X3` | full registry complete with no material caveat; closest row to `X1`, but the admitted read still keeps `X1` slightly ahead |
| `3` | `X2` | full registry complete, but still carries the `T29` widening penalty |

## Evidence basis

| Row | Evidence |
|---|---|
| `X1` | `Evidence/x1-worker-heavy-first-batch-2026-04-17.md`, `Evidence/x1-remaining-core-batch-2026-04-17.md`, `Evidence/x1-x3-extended-batch-2026-04-17.md` |
| `X2` | `Evidence/x2-worker-heavy-first-batch-2026-04-17.md`, `Evidence/x2-remaining-core-batch-2026-04-17.md`, `Evidence/x1-x3-extended-batch-2026-04-17.md` |
| `X3` | `Evidence/x3-worker-heavy-first-batch-2026-04-17.md`, `Evidence/x3-remaining-core-batch-2026-04-17.md`, `Evidence/x1-x3-extended-batch-2026-04-17.md` |

## Boundary note

This is a historical execution-backed result surface for the old upgraded-pack architecture.

The smaller steady-state core pack was the main admitted ranking surface for that legacy architecture,
but current benchmark classification now lives in the hardened `Scenarios-v2` surfaces.

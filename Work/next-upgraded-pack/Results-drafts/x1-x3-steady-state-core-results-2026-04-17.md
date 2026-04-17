Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file records the current **steady-state core execution surface** for `X1`, `X2`, and `X3`.

Unlike the earlier runnable-pack result surface, this file is aligned to the admitted core pack
from `Planning/next-phase/core-execution-pack-2026-04-17.md`.

## Scope

| Field | Value |
|---|---|
| active rows | `X1`, `X2`, `X3` |
| result surface | steady-state core execution pack |
| total core tests | `18` |
| included tests | `T01`, `T03`, `T05`, `T07`, `T08`, `T09`, `T10`, `T12`, `T15`, `T18`, `T19`, `T21`, `T22`, `T23`, `T24`, `T25`, `T29`, `T30` |
| completed rows | `X1`, `X2` |
| partially blocked row | `X3` |

## Coverage summary

| Row | Completed core tests | Status | Caveats | Read |
|---|---:|---|---|---|
| `X1` | `18 / 18` | `COMPLETE` | none material | cleanest complete steady-state core row |
| `X2` | `18 / 18` | `COMPLETE` | `T29` still carries the earlier toolchain-discipline penalty | full steady-state core green, but not as clean as `X1` |
| `X3` | `9 / 18` completed, `9 / 18` blocked | `BLOCKED` | provider quota blocked the remaining-core slice | earlier completed core slice is green, but the row is not yet full-core complete |

## Per-test result table

| `#` | Test | `X1` | `X2` | `X3` | Notes |
|---|---|---|---|---|---|
| `1` | `T01` | `PASS` | `PASS` | `BLOCKED` | `X3` remaining-core attempt emitted only the provider quota banner |
| `2` | `T03` | `PASS` | `PASS` | `BLOCKED` | same `X3` provider-quota block |
| `3` | `T05` | `PASS` | `PASS` | `BLOCKED` | same `X3` provider-quota block |
| `4` | `T07` | `PASS` | `PASS` | `BLOCKED` | same `X3` provider-quota block |
| `5` | `T08` | `PASS` | `PASS` | `PASS` | broad implementation anchor is green across all three rows |
| `6` | `T09` | `PASS` | `PASS` | `PASS` | root-cause and ownership anchor is green across all three rows |
| `7` | `T10` | `PASS` | `PASS` | `PASS` | resume and long-horizon hybrid anchor is green across all three rows |
| `8` | `T12` | `PASS` | `PASS` | `BLOCKED` | same `X3` provider-quota block |
| `9` | `T15` | `PASS` | `PASS` | `BLOCKED` | same `X3` provider-quota block |
| `10` | `T18` | `PASS` | `PASS` | `BLOCKED` | same `X3` provider-quota block |
| `11` | `T19` | `PASS` | `PASS` | `BLOCKED` | same `X3` provider-quota block |
| `12` | `T21` | `PASS` | `PASS` | `BLOCKED` | same `X3` provider-quota block |
| `13` | `T22` | `PASS` | `PASS` | `PASS` | build-owner continuity stays green across all three rows |
| `14` | `T23` | `PASS` | `PASS` | `PASS` | path-recall continuity stays green across all three rows |
| `15` | `T24` | `PASS` | `PASS` | `PASS` | multi-step persistence stays green across all three rows |
| `16` | `T25` | `PASS` | `PASS` | `PASS` | messy worker ownership stays green across all three rows |
| `17` | `T29` | `PASS` | `PASS*` | `PASS` | `X2` widened into `src/runToolchainTask.js`, so the row still carries a toolchain-discipline penalty |
| `18` | `T30` | `PASS` | `PASS` | `PASS` | stronger static UI probe stays green across all three rows |

## Current completed-row ordering

| Rank | Row | Why |
|---|---|---|
| `1` | `X1` | full steady-state core complete with no material caveat |
| `2` | `X2` | full steady-state core complete, but still carries the `T29` widening penalty |
| `3` | `X3` | not rankable on the full steady-state core until the blocked remaining-core slice is rerun |

## Evidence basis

| Row | Evidence |
|---|---|
| `X1` | `Evidence/x1-worker-heavy-first-batch-2026-04-17.md`, `Evidence/x1-remaining-core-batch-2026-04-17.md` |
| `X2` | `Evidence/x2-worker-heavy-first-batch-2026-04-17.md`, `Evidence/x2-remaining-core-batch-2026-04-17.md` |
| `X3` | `Evidence/x3-worker-heavy-first-batch-2026-04-17.md`, `Evidence/x3-remaining-core-batch-2026-04-17.md` |

## Boundary note

This is the best current steady-state core read we can admit today.

It is sufficient to say:

- `X1` and `X2` now have full steady-state core completion
- `X3` remains green on the already completed worker-heavy half of the core
- the missing `X3` half is blocked by provider quota, not by a benchmark fail

It is not sufficient to publish a final three-row full-core ranking that places `X3` relative to
`X1` and `X2` with the same confidence as a completed row.

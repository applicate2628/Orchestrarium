Date: 2026-04-20
Owner: `$lead`
Status: `PASS`

## Result

This is the current result surface for the `worker.long-autonomous` reference extra lane.

It does not replace the core `12`-lane result surface. The core routing result remains
`S01..S33 + N01..N07`; this file tracks only `E1 worker.long-autonomous` over `N08..N10`.

## Baseline extra-lane ranking

This table is the first materialized `N08..N10` baseline. It is retained as evidence that the lane
is scoreable across the wider cohort, but the tightened `X1/X3/X5` tiebreaker below is the current
read for the strengthened scenario version.

| Rank | Row | Label | Score | Read |
|---:|---|---|---:|---|
| `1` | `X3` | `opus 4.7max` | `3 / 3` | clean sweep |
| `1` | `X1` | `gpt-5.4` | `3 / 3` | clean sweep |
| `1` | `X5` | `gemini3.1pro` | `3 / 3` | clean sweep |
| `4` | `X6` | `gemini3.1flash-lite-preview` | `2 / 3` | failed `N09` continuity-null case |
| `5` | `X2` | `gpt-spark` | `1 / 3` | no-op acknowledgement on `N08` and `N10` |
| `N/A` | `X4` | `Claude China` | `0 / 0` | `NOT-RUN`; secret-backed route returned provider `502` |

## Baseline scenario matrix

| Row | Label | `N08` autonomous owner continuity | `N09` resume path recall | `N10` no-drift multi-step patch |
|---|---|---|---|---|
| `X1` | `gpt-5.4` | `PASS` | `PASS` | `PASS` |
| `X2` | `gpt-spark` | `FAIL` | `PASS` | `FAIL` |
| `X3` | `opus 4.7max` | `PASS` | `PASS` | `PASS` |
| `X4` | `Claude China` | `NOT-RUN` | `NOT-RUN` | `NOT-RUN` |
| `X5` | `gemini3.1pro` | `PASS` | `PASS` | `PASS` |
| `X6` | `gemini3.1flash-lite-preview` | `PASS` | `FAIL` | `PASS` |

## Hardened `X1/X3/X5` tiebreaker

After the baseline tied `X1`, `X3`, and `X5`, the scenario assertions were tightened for owner
continuity, resume-path recall, and no-drift patch planning.

| Row | Label | `N08` | `N09` | `N10` | Scoreable read | Current status |
|---|---|---|---|---|---:|---|
| `X1` | `gpt-5.4` | `PASS` | `PASS` | `PASS` | `3 / 3` | scoreable |
| `X3` | `opus 4.7max` | `PASS` | `PASS` | `PASS` | `3 / 3` | scoreable after provider reset |
| `X5` | `gemini3.1pro` | `PASS` | `PASS` | `PASS` | `3 / 3` | scoreable |

The earlier `X3` hardened failures in the raw batch were not verifier-level model failures: each
worker output was `You've hit your limit · resets 3am (Europe/Moscow)` and changed no benchmark
files. The post-reset rerun completed as `3 / 3 PASS`.

## Failure notes

| Row | Scenario | Cause |
|---|---|---|
| `X2` | `N08` | wrapper exited `0`, but changed `0` benchmark paths and failed `check_long_autonomous_build_owner.py` |
| `X2` | `N10` | wrapper exited `0`, but changed `0` benchmark paths and failed `check_constrained_multi_step_patch.py` |
| `X6` | `N09` | verifier expected `null` when no viable continuity signal exists, but got `docs/project-mirror` |
| `X4` | `N08..N10` | provider route returned `502 unknown provider for model claude-opus-4-7`; treated as `NOT-RUN`, not `FAIL` |

## Source

| Source | Role |
|---|---|
| `../Evidence/x1-x2-x3-x5-x6-v2-n08-n10-worker-long-autonomous-2026-04-20.md` | admitted extra-lane evidence and raw run roots |
| `../Evidence/x1-x3-x5-v2-n08-n10-worker-long-autonomous-hardened-2026-04-20.md` | tightened `X1/X3/X5` tiebreaker evidence and quota-aware rerun status |
| `benchmarks/.scratch/v2-cohort-runs/2026-04-20_05-18-03-X3-x3-n08-n10-hardened2-requeue-2026-04-20/batch-summary.md` | post-reset `X3` hardened rerun source |
| `../Planning/next-phase/12-lane-routing-translation-v1-2026-04-18.md` | benchmark-side routing translation with `E1` extra-lane basis |
| `../../../Scenarios-v2/N08-autonomous-build-owner-continuity/` | materialized `N08` scenario root |
| `../../../Scenarios-v2/N09-autonomous-resume-path-recall/` | materialized `N09` scenario root |
| `../../../Scenarios-v2/N10-constrained-multi-step-patch-no-drift/` | materialized `N10` scenario root |

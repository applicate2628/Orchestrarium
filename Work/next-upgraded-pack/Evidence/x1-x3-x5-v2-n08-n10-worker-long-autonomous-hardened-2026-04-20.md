Date: 2026-04-20
Owner: `$lead`
Status: `PASS`

## Scope

This file records the tightened tiebreaker run for the `E1 worker.long-autonomous` reference
extra lane over `N08..N10`.

The original `N08..N10` run proved the lane is scoreable. This pass tightened the assertions after
`X1`, `X3`, and `X5` all passed the first materialized version.

Provider quota, usage-limit, and reset-window messages remain `NOT-RUN` / `REQUEUE`, not scoreable
`FAIL`.

## Scenario hardening

| Scenario | Hardened checks added |
|---|---|
| `N08` | reject `src`-shaped decoys, enforce path-boundary root matching, choose the deepest overlapping manifest root, return `null` for mirror-only manifests, and support non-`workspace` roots such as `packages/editor-app` |
| `N09` | normalize the previous root, ignore stale previous roots, fall back to current-root evidence, accept prior real edit evidence, and reject mirror-only continuity guesses |
| `N10` | reject sibling-prefix paths, normalize Windows separators, allow nested files under `ownerScope`, return `null` when no in-scope candidate exists, preserve previous steps, avoid input-state mutation, clone verification-command arrays, and preserve extra command metadata |

## Hardened run roots

| Row | Label | Scratch root |
|---|---|---|
| `X1` | `gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-20_02-00-54-X1-x1-n08-n10-hardened2-2026-04-20/` |
| `X3` | `opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-20_02-00-55-X3-x3-n08-n10-hardened2-2026-04-20/` |
| `X3` post-reset rerun | `opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-20_05-18-03-X3-x3-n08-n10-hardened2-requeue-2026-04-20/` |
| `X5` | `gemini3.1pro` | `.scratch/v2-cohort-runs/2026-04-20_02-00-55-X5-x5-n08-n10-hardened2-2026-04-20/` |

## Hardened tiebreaker matrix

| Row | Label | `N08` | `N09` | `N10` | Scoreable read |
|---|---|---|---|---|---:|
| `X1` | `gpt-5.4` | `PASS` | `PASS` | `PASS` | `3 / 3` |
| `X3` | `opus 4.7max` | `PASS` | `PASS` | `PASS` | `3 / 3` |
| `X5` | `gemini3.1pro` | `PASS` | `PASS` | `PASS` | `3 / 3` |

## Quota read before post-reset rerun

| Row | Scenario | Worker output | Scoring decision |
|---|---|---|---|
| `X3` | `N08` | `You've hit your limit · resets 3am (Europe/Moscow)` | `REQUEUE`, not `FAIL` |
| `X3` | `N09` | `You've hit your limit · resets 3am (Europe/Moscow)` | `REQUEUE`, not `FAIL` |
| `X3` | `N10` | `You've hit your limit · resets 3am (Europe/Moscow)` | `REQUEUE`, not `FAIL` |

The post-reset rerun root `2026-04-20_05-18-03-X3-x3-n08-n10-hardened2-requeue-2026-04-20`
completed all three cells as `PASS`.

## Local verification

| Check | Result |
|---|---|
| `python ...N08...check_long_autonomous_build_owner.py --bundle-shape-only` | `PASS` |
| `python ...N08...check_long_autonomous_build_owner.py --expect-start-state` | `PASS` |
| `python ...N09...check_autonomous_resume_path_recall.py --bundle-shape-only` | `PASS` |
| `python ...N09...check_autonomous_resume_path_recall.py --expect-start-state` | `PASS` |
| `python ...N10...check_constrained_multi_step_patch.py --bundle-shape-only` | `PASS` |
| `python ...N10...check_constrained_multi_step_patch.py --expect-start-state` | `PASS` |
| robust known-good scratch solution over hardened `N08..N10` | `PASS` for all three scenarios |

## Current read

`PASS` for the scenario hardening itself: the tightened fixtures are valid, start-state clean, and
achievable by a robust solution.

`PASS` for the full `X1/X3/X5` tiebreaker: `X1`, `X3`, and `X5` all pass `3 / 3` on the
tightened `worker.long-autonomous` extra lane. This extra lane still does not separate the top
three rows.

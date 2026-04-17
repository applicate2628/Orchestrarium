Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This directory holds mutable execution helpers for the upgraded benchmark pack.

These helpers exist only for the active mutable workspace. They must not rewrite the
archived baseline under `Archive/`.

## Current contents

| Path | Purpose |
|---|---|
| `run-active-cohort-batch.ps1` | clones canonical `broken/` fixtures into ignored run sandboxes, launches one active-cohort row sequentially, and performs local post-run verification |
| `HOW-TO-USE-TESTS.md` | human-facing instructions for inspecting fixtures, running batches, and reading outputs |

## Current execution rule

| Rule | Meaning |
|---|---|
| canonical fixtures stay immutable | model runs happen only inside ignored `.scratch/active-cohort-runs/` sandboxes |
| one row at a time | active cohort rows are run sequentially for cleaner evidence and easier attribution |
| one completed pass, one commit | once a row pass is interpreted and written into mutable evidence, commit it before moving on |

## First admitted batch

The current helper defaults to the first worker-heavy admitted execution slice:

1. `T08`
2. `T09`
3. `T10`
4. `T22`
5. `T23`
6. `T24`
7. `T25`
8. `T29`
9. `T30`

## Human usage

| Need | Go to |
|---|---|
| quick start for running one row | `HOW-TO-USE-TESTS.md` |
| current ranked result surface | `../Results-drafts/short-results-current-2026-04-17.md` |
| live checkpoint and next action | `../Checkpoints/status-2026-04-16.md` |

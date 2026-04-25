Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This is the active mutable workspace for the next upgraded benchmark pack.

It is allowed to change freely while designing and executing the next wave.

## Current contents

| Path | Purpose |
|---|---|
| `Planning/` | next-phase design and fixture backlog |
| `Fixtures/` | mutable upgraded-fixture area |
| `Evidence/` | mutable run evidence for the next pack |
| `Checkpoints/` | mutable interpretation and status layer |
| `Results-drafts/` | draft result surfaces before archival admission |
| `Tooling/` | mutable execution helpers for active-cohort runs |

## Current live checkpoint

| File | Role |
|---|---|
| `Results-drafts/short-results-current-2026-04-18.md` | compact operator-facing current table |
| `Results-drafts/full-v2-hard-results-current.md` | current canonical hardened `/40` ranking surface |
| `Results-drafts/v2-full-s01-s33-n01-n07-results-2026-04-18.md` | deprecated pre-v3 full-v2 baseline; retained only as historical provenance |
| `Results-drafts/v2-extra-lane-n08-n10-results-2026-04-20.md` | reference extra-lane result surface for `E1 worker.long-autonomous`; `X4` deferred while the secret-backed route is unavailable |
| `Results-drafts/x1-x3-steady-state-core-results-2026-04-17.md` | legacy upgraded-pack ranking surface |
| `Results-drafts/x1-x3-current-runnable-pack-results-2026-04-17.md` | legacy supporting runnable-pack surface |
| `Checkpoints/status-2026-04-16.md` | live resume point and active obligations |

## How to use the tests

| File | Role |
|---|---|
| `Tooling/HOW-TO-USE-TESTS.md` | human-facing run guide |
| `Tooling/README.md` | tooling boundary and helper summary |
| `Tooling/run-active-cohort-batch.ps1` | active batch runner |

## Boundary

This workspace may use the archived baseline as input, but it must not silently rewrite the archived snapshot under `Archive/`.

## Current model-version note

| Surface | Current read |
|---|---|
| active mutable `X3` path | `opus 4.7max` |
| archived baseline label | remains `opus 4.6max` because the archive is historical evidence |

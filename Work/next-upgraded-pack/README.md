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

## Boundary

This workspace may use the archived baseline as input, but it must not silently rewrite the archived snapshot under `Archive/`.

## Current model-version note

| Surface | Current read |
|---|---|
| active mutable `X3` path | `opus 4.7max` |
| archived baseline label | remains `opus 4.6max` because the archive is historical evidence |

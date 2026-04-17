Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This directory is the implementation staging area for the remaining extended retrofit batch:

- `T02`
- `T04`
- `T06`
- `T11`
- `T13`
- `T14`
- `T16`
- `T17`
- `T20`

## Scope

| Test range | Main line impact | Primary reuse source |
|---|---|---|
| `T02`, `T04`, `T06` | `L01`, `L02`, `L03` | legacy `M02`, `M04`, `M06` semantics through the structured retrofit contract |
| `T11`, `T13`, `T14` | `L02`, `L03` | early role-gap planning and scientist-style probes normalized to the shared contract |
| `T16`, `T17`, `T20` | `L05`, `L06`, `L07`, `L09` | role-gap implementation and static visual families brought under runnable local verification |

## Intended implementation rule

| Rule | Meaning |
|---|---|
| preserve role pressure | each test should keep its original benchmark role instead of collapsing into a generic memo |
| stay on the shared hardening contract | every fixture must expose `broken/`, `control-pass/`, a true owner seam, and anti-drift checks where useful |
| extended does not mean soft | these tests may sit outside the steady-state core, but they still need to be runnable and comparable |

## Current state

All nine fixtures in this batch now have:

- runnable `broken/` and `control-pass/` copies
- local verification coverage
- recorded batch validation in `Evidence/retrofit-batch-3-local-validation-2026-04-17.md`

## Next concrete action

Use the active cohort runner to execute:

- `X1`
- `X2`
- `X3`

against:

- `T02`
- `T04`
- `T06`
- `T11`
- `T13`
- `T14`
- `T16`
- `T17`
- `T20`

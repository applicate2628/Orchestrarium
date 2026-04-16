Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This file is the concrete execution plan for the next upgraded benchmark pack.

It converts the roadmap into batches, outputs, and gates.

The full registry remains `T01..T33`, but regular execution is now centered on the smaller steady-state core pack.

## Batch plan

| Batch | Focus | Allowed surfaces | Expected artifact | Gate |
|---|---|---|---|---|
| `B1` | finalize execution scaffolding | `Planning/next-phase/`, `Checkpoints/` | roadmap package plus mutable status surface | planning docs are coherent and cross-linked |
| `B2` | define retrofit batches for migrated tests | `Planning/next-phase/`, later `Fixtures/` | retrofit batch spec for the worker-heavy core slice and its nearest migrated dependencies | every selected core test has an implementation-ready action |
| `B3` | design first upgraded probes | `Planning/next-phase/`, later `Fixtures/` | accepted fixture spec for `T29` and `T30` | spec is specific enough to implement and validate |
| `B4` | implement first fixture batch | `Fixtures/` | concrete fixture and verifier package for the worker-heavy core slice | local broken-state and control-pass evidence passes |
| `B5` | run active execution cohort | `Evidence/` | run evidence for `X1`, `X2`, `X3` on the first batch | each run has enough evidence to support interpretation |
| `B6` | interpret first batch | `Checkpoints/`, `Results-drafts/` | updated mutable checkpoint plus first draft ranking surface | changes are evidence-backed and mapped to `L` lines |
| `B7` | widen or admit | all mutable next-pack surfaces | decision memo: complete the rest of the core pack, widen into the extended pack, or prepare archive candidate | next action is explicit and bounded |

## Steady-state execution tiers

| Tier | Scope |
|---|---|
| core | `T01`, `T03`, `T05`, `T07`, `T08`, `T09`, `T10`, `T12`, `T15`, `T18`, `T19`, `T21`, `T22`, `T23`, `T24`, `T25`, `T29`, `T30` |
| extended | `T02`, `T04`, `T06`, `T11`, `T13`, `T14`, `T16`, `T17`, `T20`, `T26`, `T27`, `T28` |
| incubation | `T31`, `T32`, `T33` |

## First admitted execution slice

| Order | Target |
|---|---|
| `1` | complete the worker-heavy core slice: `T08`, `T09`, `T10`, `T22`, `T23`, `T24`, `T25`, `T29`, `T30` |
| `2` | complete the advisory, review, and static-core slice: `T01`, `T03`, `T05`, `T07`, `T12`, `T15`, `T18`, `T19`, `T21` |
| `3` | run `X1`, `X2`, `X3` on the resulting core pack |
| `4` | widen into the extended pack only if the core leaves unresolved ties or suspicious rank shifts |

## Stop conditions

| Condition | Action |
|---|---|
| mapping drift or unresolved ID conflict | stop the current batch and fix planning first |
| fixture cannot show broken-state or control-pass evidence | do not run models yet; fix the fixture |
| active cohort runtime is unhealthy | pause execution but keep planning and fixture work open |
| ranking interpretation depends on missing evidence | do not publish draft results yet |

## Default continuity rule

Once a batch passes its gate, move directly to the next batch.
Do not pause for commentary-only checkpoints unless a gate actually fails or an external blocker appears.

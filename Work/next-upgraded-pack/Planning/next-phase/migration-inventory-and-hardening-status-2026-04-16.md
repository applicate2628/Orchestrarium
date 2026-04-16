Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This file is the migration inventory for the upgraded benchmark pack.

It does three jobs together:

1. maps every legacy test or synthesis alias to its upgraded-pack ID
2. shows which `L` lines consume that evidence
3. assigns the planned hardening action for migration

The full registry in this file is intentionally larger than the future steady-state execution surface.
Regular reruns should use the smaller core pack defined in `core-execution-pack-2026-04-17.md`.

## Status legend

| Status | Meaning |
|---|---|
| `retrofit-required` | migrate the legacy test into the shared hardening contract |
| `normalize-required` | keep the test but align it to the upgraded naming and hardening contract |
| `overlay-only` | keep as overlay or provenance surface, not as an atomic test |

## Migrated legacy matrix tests

| Upgraded ID | Legacy alias | Feeds lines | Planned hardening status | Priority |
|---|---|---|---|---|
| `T01` | `M01` | `L01` | `retrofit-required` | `P2` |
| `T02` | `M02` | `L01`, `L02` | `retrofit-required` | `P2` |
| `T03` | `M03` | `L02`, `L03` | `retrofit-required` | `P2` |
| `T04` | `M04` | `L02` | `retrofit-required` | `P3` |
| `T05` | `M05` | `L04`, `L05`, `L09` | `retrofit-required` | `P2` |
| `T06` | `M06` | `L03` | `retrofit-required` | `P3` |
| `T07` | `M07` | `L03`, `L07` | `retrofit-required` | `P2` |
| `T08` | `M08` | `L06`, `L07`, `L09` | `retrofit-required` | `P1` |
| `T09` | `M09` | `L06`, `L07`, `L08` | `retrofit-required` | `P1` |
| `T10` | `M10` | `L02`, `L08`, `L10` | `retrofit-required` | `P1` |

## Migrated legacy role-gap and trust tests

| Upgraded ID | Legacy alias | Feeds lines | Planned hardening status | Priority |
|---|---|---|---|---|
| `T11` | `G01` | `L02` | `normalize-required` | `P3` |
| `T12` | `G02` | `L01` | `normalize-required` | `P3` |
| `T13` | `G03` | `L02`, `L03` | `normalize-required` | `P3` |
| `T14` | `G04` | `L02`, `L03` | `normalize-required` | `P3` |
| `T15` | `G05` | `L07`, `L08` | `normalize-required` | `P2` |
| `T16` | `G06` | `L06`, `L07` | `normalize-required` | `P2` |
| `T17` | `G07` | `L06`, `L09` | `normalize-required` | `P2` |
| `T18` | `G08` | `L05` | `normalize-required` | `P2` |
| `T19` | `G09` | `L04` | `normalize-required` | `P2` |
| `T20` | `G10` | `L05`, `L09` | `normalize-required` | `P2` |
| `T21` | `G11` | `L06`, `L09` | `normalize-required` | `P2` |
| `T22` | `G12` | `L08`, `L10` | `normalize-required` | `P1` |
| `T23` | `G13` | `L09`, `L10` | `normalize-required` | `P1` |
| `T24` | `G14` | `L10` | `normalize-required` | `P1` |
| `T25` | `G15` | `L07`, `L08`, `L10` | `normalize-required` | `P1` |
| `T26` | `G16` | `L08` | `normalize-required` | `P1` |
| `T27` | `G17` | `L10` | `normalize-required` | `P1` |
| `T28` | `G18` | `L10` | `normalize-required` | `P1` |

## Legacy synthesis overlays

| Upgraded ID | Legacy alias | Future status | Main use |
|---|---|---|---|
| `O01` | `W1` | `overlay-only` | provenance for historical advisory and review-heavy top-path synthesis |
| `O02` | `W2` | `overlay-only` | provenance for historical reasoning and risk top-path synthesis |
| `O03` | `W3` | `overlay-only` | provenance for historical bounded worker top-path synthesis |
| `O04` | `W4` | `overlay-only` | fallback mechanical overlay |
| `O05` | `W5` | `overlay-only` | fallback reasoning overlay |

## New upgraded-pack candidate tests

| Upgraded ID | Working name | Feeds lines or overlays | Planned status |
|---|---|---|---|
| `T29` | toolchain false-root ambiguity | `L08` | `new-design` |
| `T30` | static UI wrong-file attraction | `L05`, `L09` | `new-design` |
| `T31` | fallback noisy-evidence filter | `O04`, `O05` | `new-design` |
| `T32` | constrained multi-step patch with no drift | `L06`, `L07` | `new-design` |
| `T33` | decorative consistency with asset distractors | `L09` | `new-design` |

## First recommended execution block

| Order | Focus |
|---|---|
| `1` | inventory and retrofit `T08..T10` plus `T22..T28` because they feed the most fragile worker lines |
| `2` | normalize `T15..T21` because they shape implementation and UI lines |
| `3` | backfill `T01..T07` and `T11..T14` once the worker side is stable |
| `4` | design and admit `T29..T30` before widening to the rest of the new backlog |

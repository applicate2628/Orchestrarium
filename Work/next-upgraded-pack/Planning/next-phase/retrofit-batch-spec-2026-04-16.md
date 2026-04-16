Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This file is the first retrofit batch specification for the upgraded benchmark pack.

It defines the first implementation-ready retrofit scope for migrated tests:

- `T08..T10`
- `T22..T28`

## Batch objective

Bring the most worker-critical migrated legacy tests under the upgraded hardening contract first.

## Why this batch is first

| Reason | Meaning |
|---|---|
| highest worker impact | these tests feed the most fragile worker lines |
| most ranking leverage | `L06`, `L07`, `L08`, and `L10` are the current highest-risk practical lines |
| best hardening return | these tests are where anti-hardcode, anti-drift, and owner-verification pressure matters most |

## Batch slices

| Slice | Scope | Main fed lines | Batch goal |
|---|---|---|---|
| `RB1-A` | `T08`, `T09`, `T10` | `L06`, `L07`, `L08`, `L10` | retrofit migrated legacy matrix worker tests into the upgraded hardening contract |
| `RB1-B` | `T22`, `T23`, `T24`, `T25`, `T26`, `T27`, `T28` | `L08`, `L09`, `L10` | normalize trust, continuity, and ownership probes into one consistent upgraded contract |

## Per-test retrofit intent

| Test | Legacy alias | Main fed lines | Required retrofit |
|---|---|---|---|
| `T08` | `M08` | `L06`, `L07`, `L09` | add stronger true-owner verification, anti-drift checks, and wrong-file attraction |
| `T09` | `M09` | `L06`, `L07`, `L08` | strengthen root-cause and owner verification while punishing brittle local fixes |
| `T10` | `M10` | `L02`, `L08`, `L10` | unify resume and stale-context pressure with the upgraded autonomy contract |
| `T22` | `G12` | `L08`, `L10` | strengthen build-owner discovery with false-root and false-owner decoys |
| `T23` | `G13` | `L09`, `L10` | strengthen late-session recall with distractor edit points and continuity checks |
| `T24` | `G14` | `L10` | normalize multi-step persistence against anti-shortcut rules |
| `T25` | `G15` | `L07`, `L08`, `L10` | preserve messy ownership pressure and explicitly reject brittle exact-path logic |
| `T26` | `G16` | `L08` | normalize toolchain-owner ambiguity under the shared contract |
| `T27` | `G17` | `L10` | normalize late-session recall under the shared contract |
| `T28` | `G18` | `L10` | normalize reviewer-to-worker transition under the shared contract |

## Shared retrofit acceptance criteria

| Requirement | Meaning |
|---|---|
| broken-state evidence | each migrated test must show a real failing start state |
| control-pass evidence | each migrated test must show a validated correct state |
| true-owner verification | passing requires the actual owning file or seam |
| anti-hardcode | brittle path-specific or repo-specific cheats should fail |
| anti-drift | unrelated visible contracts and tests must stay intact |
| naming normalization | mutable docs should refer to these tests primarily as `T` IDs |

## Implementation-ready constraints

| Constraint | Meaning |
|---|---|
| mutate only mutable next-pack surfaces | changes belong under `Work/next-upgraded-pack/` |
| preserve archive references | do not silently rewrite archived baseline docs |
| prefer smallest safe fixture delta | retrofit legacy tests instead of rewriting them from scratch without reason |
| keep line mapping stable | if a retrofit changes line feeding, update the migration inventory before execution continues |

## Expected outputs

| Output | Destination |
|---|---|
| retrofit notes per selected test | `Planning/next-phase/` or fixture-local notes |
| implemented fixture and verifier deltas | `Fixtures/` |
| local validation evidence | `Evidence/` later, after implementation |

## Gate to implementation

This batch is ready to enter implementation when:

1. no unresolved `T`-ID drift remains
2. each selected test has a concrete retrofit delta
3. `T29` and `T30` probe specs exist as the parallel first upgraded probes

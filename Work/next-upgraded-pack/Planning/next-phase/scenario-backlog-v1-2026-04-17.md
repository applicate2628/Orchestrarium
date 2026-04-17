Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file defines the milestone-1 seed scenario backlog for the role-complete benchmark redesign.

It translates the accepted role matrix and pack architecture into one planned scenario bundle per
benchmark surface so fixture-building can begin without reopening the role taxonomy.

## Backlog rules

| Rule | Meaning |
|---|---|
| one seed per surface | every `R01..R31` and `A01..A02` gets exactly one milestone-1 seed scenario |
| packs stay exact | scenario membership follows the accepted `P01..P07` pack model with no extra role merges |
| non-web-first | only `S16` is intrinsically web implementation; other web pressure stays role-fit and optional |
| adapters stay separate | `S32` and `S33` benchmark transport fidelity only and do not stand in for semantic role ability |
| legacy checkpoint only | old `T/L/O` assets may inspire future fixtures, but they do not define v2 scenario identity |

## Scenario root convention

Planned bundle roots should use:

- `Scenarios-v2/Snn-short-slug/`

The bundle contract itself is specified in `pack-specs-v1-2026-04-17.md`.

## Seed backlog

### `P01 owner-advisory`

| Scenario | Surface | Role class | Modality family | Artifact type | Archetype | Overlay flags |
|---|---|---|---|---|---|---|
| `S01` | `R01 $product-manager` | owner | roadmap and intake | roadmap decision package | roadmap prioritization under conflicting product constraints | `[]` |
| `S02` | `R02 $lead` | owner | orchestration and recovery | canonical brief and status packet | orchestration recovery, resume-point, and artifact routing packet | `[]` |
| `S03` | `R03 $consultant` | advisory | tradeoff memo | advisory memo | advisory tradeoff memo with incomplete but non-empty evidence | `[]` |
| `S04` | `R04 $knowledge-archivist` | hygiene | archive and source-of-truth hygiene | source-of-truth update packet | canonical-source repair and archive hygiene task | `[]` |

### `P02 factual-design-planning`

| Scenario | Surface | Role class | Modality family | Artifact type | Archetype | Overlay flags |
|---|---|---|---|---|---|---|
| `S05` | `R05 $product-analyst` | factual | product framing | product brief | product brief from noisy intake notes | `[]` |
| `S06` | `R06 $analyst` | factual | repository investigation | factual research memo | repository fact extraction with decoys and false leads | `[]` |
| `S07` | `R07 $architect` | design | architecture decision | ADR or design package | ADR package with multiple plausible seams | `[]` |
| `S08` | `R08 $ux-designer` | design | interaction design | UX structure brief | UX restructuring for a mixed desktop/web interaction problem | `[]` |
| `S09` | `R09 $planner` | planning | phased delivery planning | phase plan | phased plan from accepted brief, design, and constraints | `[]` |

### `P03 scientist-constraints`

| Scenario | Surface | Role class | Modality family | Artifact type | Archetype | Overlay flags |
|---|---|---|---|---|---|---|
| `S10` | `R10 $algorithm-scientist` | scientist | formal reasoning | invariant and proof memo | invariant and proof-framing memo | `[]` |
| `S11` | `R11 $computational-scientist` | scientist | numerical or physical reasoning | model and validation memo | numerical or physical model validation memo | `[]` |
| `S12` | `R12 $security-engineer` | constraint | threat and trust analysis | security constraint package | threat-model and trust-boundary package | `[]` |
| `S13` | `R13 $performance-engineer` | constraint | budget and bottleneck analysis | performance constraint package | bottleneck and budget analysis package | `[]` |
| `S14` | `R14 $reliability-engineer` | constraint | failure and rollout analysis | reliability constraint package | rollout, failure-mode, and rollback package | `[]` |

### `P04 implementation-general`

| Scenario | Surface | Role class | Modality family | Artifact type | Archetype | Overlay flags |
|---|---|---|---|---|---|---|
| `S15` | `R15 $backend-engineer` | implementation | backend code | code patch plus local verification | backend owner-seam code patch | `[]` |
| `S16` | `R16 $frontend-engineer` | implementation | web UI | code patch plus local verification | web UI code patch | `[browser-required]` |
| `S19` | `R19 $data-engineer` | implementation | SQL, ETL, or data pipeline | code or query patch plus validation | data pipeline, SQL, or migration patch | `[]` |
| `S20` | `R20 $platform-engineer` | implementation | CI, deployment, or observability | config patch plus validation | CI, deployment, or observability patch | `[]` |
| `S21` | `R21 $toolchain-engineer` | implementation | build and packaging | toolchain patch plus validation | build-graph or toolchain ownership patch | `[]` |

### `P05 implementation-specialty`

| Scenario | Surface | Role class | Modality family | Artifact type | Archetype | Overlay flags |
|---|---|---|---|---|---|---|
| `S17` | `R17 $qt-ui-engineer` | implementation | Qt desktop UI | code patch plus local verification | Qt desktop UI code patch | `[]` |
| `S18` | `R18 $model-view-engineer` | implementation | Qt model/view | code patch plus local verification | Qt model/view correctness patch | `[]` |
| `S22` | `R22 $geometry-engineer` | implementation | geometry or transforms | code patch plus validation | geometry predicate or transform patch | `[]` |
| `S23` | `R23 $graphics-engineer` | implementation | rendering or graphics pipeline | code patch plus validation | rendering or graphics pipeline patch | `[]` |
| `S24` | `R24 $visualization-engineer` | implementation | scientific or data visualization | code patch plus validation | visualization interpretation or rendering patch | `[]` |

### `P06 review-qa`

| Scenario | Surface | Role class | Modality family | Artifact type | Archetype | Overlay flags |
|---|---|---|---|---|---|---|
| `S25` | `R25 $qa-engineer` | review | verification and test design | QA report and test verdict | QA verification and acceptance report | `[]` |
| `S26` | `R26 $architecture-reviewer` | review | maintainability gate | review findings | architecture review findings | `[]` |
| `S27` | `R27 $security-reviewer` | review | security gate | review findings | security review findings | `[]` |
| `S28` | `R28 $performance-reviewer` | review | performance gate | review findings | performance review findings | `[]` |
| `S29` | `R29 $accessibility-reviewer` | review | accessibility gate | review findings | accessibility review findings | `[]` |
| `S30` | `R30 $ux-reviewer` | review | UX gate | review findings | UX review findings | `[]` |
| `S31` | `R31 $ui-test-engineer` | review | UI regression verification | UI test report | UI regression test report | `[]` |

### `P07 transport-adapters`

| Scenario | Surface | Role class | Modality family | Artifact type | Archetype | Overlay flags |
|---|---|---|---|---|---|---|
| `S32` | `A01 $external-worker` | adapter | transport fidelity | transport execution report | external-worker routing fidelity and output cleanliness | `[external-transport]` |
| `S33` | `A02 $external-reviewer` | adapter | transport fidelity | transport execution report | external-reviewer routing fidelity and output cleanliness | `[external-transport]` |

## Coverage and balance check

| Check | Read |
|---|---|
| role coverage | `R01..R31` appear exactly once in the seed backlog |
| adapter coverage | `A01..A02` appear exactly once in the seed backlog |
| total seed scenarios | `33` |
| pack coverage | `P01..P07` all have explicit seed members |
| non-web balance | every pack has at least one non-web-shaped scenario; only `S16` is intrinsically browser-bound |
| adapter separation | transport scenarios are isolated in `P07` and do not appear in semantic packs |

## Pack-level modality read

| Pack | Non-web scenarios present | Read |
|---|---|---|
| `P01` | `S01`, `S02`, `S03`, `S04` | fully non-web |
| `P02` | `S05`, `S06`, `S07`, `S09` | mixed, with non-web majority |
| `P03` | `S10`, `S11`, `S12`, `S13`, `S14` | fully non-web |
| `P04` | `S15`, `S19`, `S20`, `S21` | one intrinsic web scenario only |
| `P05` | `S17`, `S18`, `S22`, `S23`, `S24` | fully non-web |
| `P06` | `S25`, `S26`, `S27`, `S28`, `S29`, `S30`, `S31` | mixed review surfaces without browser dominance |
| `P07` | `S32`, `S33` | transport-only, non-web |

## Consequence

This backlog becomes the milestone-1 planning source of truth for:

- future bundle skeleton creation
- per-role publication tables
- pack admission order
- scoring profile assignment

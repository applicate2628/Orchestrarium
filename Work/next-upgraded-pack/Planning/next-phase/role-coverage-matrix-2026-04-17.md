Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file defines the benchmark coverage universe for the role-complete redesign.

It uses the current `AGENTS.md` role index as the source of truth and separates:

- semantic roles
- transport adapters

## Coverage model

| Category | Count | Meaning |
|---|---:|---|
| semantic roles | `31` | roles whose benchmark should measure actual role ability |
| transport adapters | `2` | roles whose benchmark should measure routing, runtime, and contract faithfulness rather than semantic skill |
| total named benchmark surfaces | `33` | full current benchmark universe from `AGENTS.md` |

## Semantic role matrix

| ID | Role | Role class | Primary benchmark modality | Expected artifact type |
|---|---|---|---|---|
| `R01` | `$product-manager` | owner | intake and prioritization | roadmap decision package |
| `R02` | `$lead` | owner | orchestration and recovery | canonical brief and status packet |
| `R03` | `$consultant` | advisory | tradeoff analysis | advisory memo |
| `R04` | `$knowledge-archivist` | hygiene | canonical-source maintenance | archive or source-of-truth update packet |
| `R05` | `$product-analyst` | factual | product framing | product brief |
| `R06` | `$analyst` | factual | repository investigation | factual research memo |
| `R07` | `$architect` | design | architecture decision | ADR or design package |
| `R08` | `$ux-designer` | design | interaction design | UX structure brief |
| `R09` | `$planner` | planning | phased delivery planning | phase plan |
| `R10` | `$algorithm-scientist` | scientist | formal reasoning | invariant and proof memo |
| `R11` | `$computational-scientist` | scientist | numerical or physical reasoning | model and validation memo |
| `R12` | `$security-engineer` | constraint | threat and trust analysis | security constraint package |
| `R13` | `$performance-engineer` | constraint | budget and bottleneck analysis | performance constraint package |
| `R14` | `$reliability-engineer` | constraint | failure and rollout analysis | reliability constraint package |
| `R15` | `$backend-engineer` | implementation | backend code change | code patch plus local verification |
| `R16` | `$frontend-engineer` | implementation | web UI code change | code patch plus local verification |
| `R17` | `$qt-ui-engineer` | implementation | Qt desktop UI | code patch plus local verification |
| `R18` | `$model-view-engineer` | implementation | Qt model/view | code patch plus local verification |
| `R19` | `$data-engineer` | implementation | SQL, ETL, or data pipeline | code or query patch plus validation |
| `R20` | `$platform-engineer` | implementation | CI, CD, infra, or observability | config patch plus validation |
| `R21` | `$toolchain-engineer` | implementation | build and packaging | toolchain patch plus validation |
| `R22` | `$geometry-engineer` | implementation | spatial or geometric logic | code patch plus validation |
| `R23` | `$graphics-engineer` | implementation | rendering or GPU logic | code patch plus validation |
| `R24` | `$visualization-engineer` | implementation | chart or scientific visualization | code patch plus validation |
| `R25` | `$qa-engineer` | review | verification and test design | QA report and test verdict |
| `R26` | `$architecture-reviewer` | review | maintainability gate | review findings |
| `R27` | `$security-reviewer` | review | security gate | review findings |
| `R28` | `$performance-reviewer` | review | performance gate | review findings |
| `R29` | `$accessibility-reviewer` | review | accessibility gate | review findings |
| `R30` | `$ux-reviewer` | review | UX gate | review findings |
| `R31` | `$ui-test-engineer` | review | UI regression verification | UI test report |

## Transport adapter matrix

| ID | Role | Benchmark target | Expected artifact type |
|---|---|---|---|
| `A01` | `$external-worker` | routing fidelity, runtime cleanliness, contract preservation | transport execution report |
| `A02` | `$external-reviewer` | review transport fidelity, runtime cleanliness, contract preservation | transport execution report |

## Modality-balance rule

| Modality family | Must exist |
|---|---|
| owner and orchestration | yes |
| document and memo synthesis | yes |
| repository analysis | yes |
| architecture and planning | yes |
| scientist and constraint reasoning | yes |
| backend and systems code | yes |
| data and toolchain work | yes |
| web UI | yes |
| non-web UI | yes |
| graphics, geometry, and visualization | yes |
| review and QA | yes |
| archive and source-of-truth hygiene | yes |

## Consequence

The benchmark system should no longer publish only a small merged line family table.

Its main future result surface should be:

- one row per benchmarked semantic role
- optional separate transport rows for adapters

Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file defines the v1 pack specs and the scenario bundle contract for the role-complete benchmark redesign.

It is the handoff artifact that should let the next engineer materialize bundle skeletons without
reopening pack membership, artifact type, or publication boundaries.

## Universal scenario bundle contract

### Required structure

| Path | Purpose |
|---|---|
| `scenario.yaml` | source-of-truth metadata for the bundle |
| `README.md` | human-readable task contract |
| `inputs/` | immutable problem packet |
| `candidate/` | mutable run root copied per execution |
| `oracle/` | expected truths, scoring anchors, and golden references |
| `verifiers/` | local machine checks or scoring helpers |

### Required `scenario.yaml` fields

| Field | Meaning |
|---|---|
| `id` | scenario ID such as `S21` |
| `surface_id` | role or adapter surface such as `R21` or `A01` |
| `pack_id` | pack membership such as `P04` |
| `role_class` | role class from the role matrix |
| `artifact_type` | required output type |
| `modality_family` | scenario modality |
| `allowed_change_surface` | paths or artifacts the candidate may change |
| `must_not_touch` | paths or artifacts that must remain unchanged |
| `score_profile` | weight profile family from the scoring model |
| `overlay_flags` | declared overlay hooks such as `browser-required` or `external-transport` |

### Artifact-type contract

| Role family | Required artifact type |
|---|---|
| owner, advisory, factual, design, planning, hygiene | structured memo or packet output |
| scientist and constraints | structured memo or packet output |
| implementation | bounded code or config patch plus local verification |
| review and QA | findings-only review report or QA verdict |
| adapters | transport execution report |

### Contract notes

| Rule | Meaning |
|---|---|
| no universal broken/control-pass contract | use it only inside implementation scenarios when it materially improves local verification |
| review roles stay review-only | no code patching inside `P06` bundles |
| adapter roles stay transport-only | no semantic role substitution inside `P07` scoring |
| frozen history stays frozen | old upgraded-pack results may inform future scenarios but are not the candidate root |

## Pack matrix

| Pack | Purpose | Roles | Seed scenarios |
|---|---|---|---|
| `P01 owner-advisory` | prioritization, orchestration, advice, source-of-truth hygiene | `R01`, `R02`, `R03`, `R04` | `S01`, `S02`, `S03`, `S04` |
| `P02 factual-design-planning` | product framing, repo facts, design, UX, phased delivery | `R05`, `R06`, `R07`, `R08`, `R09` | `S05`, `S06`, `S07`, `S08`, `S09` |
| `P03 scientist-constraints` | formal, numerical, security, performance, reliability reasoning | `R10`, `R11`, `R12`, `R13`, `R14` | `S10`, `S11`, `S12`, `S13`, `S14` |
| `P04 implementation-general` | backend, web, data, platform, toolchain implementation | `R15`, `R16`, `R19`, `R20`, `R21` | `S15`, `S16`, `S19`, `S20`, `S21` |
| `P05 implementation-specialty` | Qt, model/view, geometry, graphics, visualization implementation | `R17`, `R18`, `R22`, `R23`, `R24` | `S17`, `S18`, `S22`, `S23`, `S24` |
| `P06 review-qa` | QA and reviewer gates | `R25`, `R26`, `R27`, `R28`, `R29`, `R30`, `R31` | `S25`, `S26`, `S27`, `S28`, `S29`, `S30`, `S31` |
| `P07 transport-adapters` | external worker and reviewer transport fidelity | `A01`, `A02` | `S32`, `S33` |

## Pack admission rules

| Pack | Required pressure |
|---|---|
| `P01` | at least one ambiguity-sensitive scenario and one orchestration-resume scenario |
| `P02` | at least one decoy-heavy factual scenario and one multi-seam design scenario |
| `P03` | entirely non-web and evidence-heavy |
| `P04` | at least one bounded owner-seam code scenario; only `S16` is intrinsically web |
| `P05` | entirely non-web specialty implementation |
| `P06` | findings-only review outputs with no hidden implementation work |
| `P07` | transport/runtime evaluation only; never merged into semantic role tables |

## Worked example bundles

### `P01` worked example: `S02 lead recovery packet`

| Field | Value |
|---|---|
| bundle root | `Scenarios-v2/S02-lead-recovery-packet/` |
| `surface_id` | `R02` |
| `pack_id` | `P01` |
| `role_class` | owner |
| `artifact_type` | canonical brief and status packet |
| `modality_family` | orchestration and recovery |
| `allowed_change_surface` | `candidate/work-items/active/...` status and routing packet only |
| `must_not_touch` | frozen results, archived evidence, unrelated fixture roots |
| `score_profile` | owner, advisory, factual, design, planning |
| `overlay_flags` | `[]` |

| Path | Planned contents |
|---|---|
| `inputs/` | interrupted status note, accepted upstream artifact set, side-request interruption record |
| `candidate/` | mutable status packet and routing memo |
| `oracle/` | correct resume point, required handoff fields, prohibited rerouting patterns |
| `verifiers/` | schema check for resume-point fields and reference integrity |

### `P02` worked example: `S07 architect multi-seam ADR`

| Field | Value |
|---|---|
| bundle root | `Scenarios-v2/S07-architect-multi-seam-adr/` |
| `surface_id` | `R07` |
| `pack_id` | `P02` |
| `role_class` | design |
| `artifact_type` | ADR or design package |
| `modality_family` | architecture decision |
| `allowed_change_surface` | design packet only |
| `must_not_touch` | implementation files, upstream factual brief, unrelated planning docs |
| `score_profile` | owner, advisory, factual, design, planning |
| `overlay_flags` | `[]` |

| Path | Planned contents |
|---|---|
| `inputs/` | accepted brief, factual repo memo, competing seam options, dependency map |
| `candidate/` | ADR packet with chosen seam and tradeoff rationale |
| `oracle/` | admissible seam list, expected tradeoff anchors, known anti-patterns |
| `verifiers/` | structural check for ADR sections and dependency-direction claims |

### `P03` worked example: `S12 security trust-boundary package`

| Field | Value |
|---|---|
| bundle root | `Scenarios-v2/S12-security-trust-boundary-package/` |
| `surface_id` | `R12` |
| `pack_id` | `P03` |
| `role_class` | constraint |
| `artifact_type` | security constraint package |
| `modality_family` | threat and trust analysis |
| `allowed_change_surface` | security memo only |
| `must_not_touch` | runtime code, dependency manifests, unrelated docs |
| `score_profile` | scientist, constraints |
| `overlay_flags` | `[]` |

| Path | Planned contents |
|---|---|
| `inputs/` | system diagram, trust boundary hints, auth flow notes, sensitive data map |
| `candidate/` | threat-model packet with required controls and must-fix constraints |
| `oracle/` | required trust boundaries, expected threat classes, disallowed hand-waving |
| `verifiers/` | package section check and control-reference completeness check |

### `P04` worked example: `S21 toolchain ownership patch`

| Field | Value |
|---|---|
| bundle root | `Scenarios-v2/S21-toolchain-ownership-patch/` |
| `surface_id` | `R21` |
| `pack_id` | `P04` |
| `role_class` | implementation |
| `artifact_type` | toolchain patch plus validation |
| `modality_family` | build and packaging |
| `allowed_change_surface` | build graph, packaging config, toolchain-owned scripts under the admitted root |
| `must_not_touch` | runtime app code, unrelated platform deployment files, result docs |
| `score_profile` | implementation |
| `overlay_flags` | `[]` |

| Path | Planned contents |
|---|---|
| `inputs/` | failing build graph, package metadata, owner map, expected artifact contract |
| `candidate/` | mutable toolchain root with bounded failing case |
| `oracle/` | intended owner seam, passing command, forbidden widening paths |
| `verifiers/` | local build or static validation command plus scope-diff helper |

### `P05` worked example: `S22 geometry predicate patch`

| Field | Value |
|---|---|
| bundle root | `Scenarios-v2/S22-geometry-predicate-patch/` |
| `surface_id` | `R22` |
| `pack_id` | `P05` |
| `role_class` | implementation |
| `artifact_type` | code patch plus validation |
| `modality_family` | geometry or transforms |
| `allowed_change_surface` | geometry module and its direct tests only |
| `must_not_touch` | graphics renderer, UI layers, unrelated benchmarks |
| `score_profile` | implementation |
| `overlay_flags` | `[]` |

| Path | Planned contents |
|---|---|
| `inputs/` | failing predicate case set, coordinate-system notes, intended invariant list |
| `candidate/` | mutable geometry module root |
| `oracle/` | truth table for edge cases, allowed numeric tolerances, prohibited bypasses |
| `verifiers/` | deterministic geometry test set and scope-diff helper |

### `P06` worked example: `S26 architecture review findings`

| Field | Value |
|---|---|
| bundle root | `Scenarios-v2/S26-architecture-review-findings/` |
| `surface_id` | `R26` |
| `pack_id` | `P06` |
| `role_class` | review |
| `artifact_type` | findings-only review report |
| `modality_family` | maintainability gate |
| `allowed_change_surface` | review report only |
| `must_not_touch` | candidate code, design packet, upstream status docs |
| `score_profile` | review, QA |
| `overlay_flags` | `[]` |

| Path | Planned contents |
|---|---|
| `inputs/` | bounded diff, accepted design packet, repo context memo, known risks |
| `candidate/` | review report template |
| `oracle/` | ground-truth findings, severity anchors, false-positive traps |
| `verifiers/` | report-shape check and finding-reference completeness check |

### `P07` worked example: `S32 external-worker transport fidelity`

| Field | Value |
|---|---|
| bundle root | `Scenarios-v2/S32-external-worker-transport-fidelity/` |
| `surface_id` | `A01` |
| `pack_id` | `P07` |
| `role_class` | adapter |
| `artifact_type` | transport execution report |
| `modality_family` | transport fidelity |
| `allowed_change_surface` | transport log and adapter report only |
| `must_not_touch` | semantic result tables, upstream planning docs, unrelated runtime wrappers |
| `score_profile` | adapters |
| `overlay_flags` | `[external-transport]` |

| Path | Planned contents |
|---|---|
| `inputs/` | assigned worker role, provider preference rules, expected artifact contract, transport wrapper notes |
| `candidate/` | adapter report template and bounded execution packet |
| `oracle/` | valid routing outcomes, required provenance fields, prohibited internal fallback patterns |
| `verifiers/` | transport report schema check and provenance-field completeness check |

## Consequence

The next fixture-building step should materialize these worked examples into real bundle roots first,
because that will validate:

- the directory contract
- the scoring-profile assignment
- the pack separation rules
- the publication boundary between semantic roles and adapters

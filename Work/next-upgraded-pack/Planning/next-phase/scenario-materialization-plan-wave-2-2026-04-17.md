Date: 2026-04-17
Owner: `$planner`
Status: `PASS`

## Purpose

This plan turns the admitted second-wave scenario set into real v2 bundle roots under
`Scenarios-v2/` without reopening taxonomy, first-wave decisions, scoring rules, or provider
execution policy.

The admitted wave stays balanced by design:

- create exactly one new real bundle from each remaining pack `P01..P07`
- write only under new sibling roots in `Scenarios-v2/`
- treat the accepted first-wave roots as reference-only, not mutable surfaces
- stop before provider reruns, scoring updates, result-table rewrites, or checkpoint changes

All paths below are relative to the benchmarks worktree root `D:/dev/Orchestrator/benchmarks/`.

## Admitted bundle set

| Pack | Scenario | Surface | Planned root | Reason for admission |
|---|---|---|---|---|
| `P01` | `S03` | `R03 $consultant` | `Scenarios-v2/S03-consultant-tradeoff-memo/` | fills the remaining advisory surface with a memo-only second-opinion bundle |
| `P02` | `S06` | `R06 $analyst` | `Scenarios-v2/S06-analyst-repository-fact-memo/` | fills the remaining factual repo-investigation surface with decoy pressure |
| `P03` | `S10` | `R10 $algorithm-scientist` | `Scenarios-v2/S10-algorithm-invariant-proof-memo/` | fills the remaining formal-reasoning surface with invariant/proof framing |
| `P04` | `S16` | `R16 $frontend-engineer` | `Scenarios-v2/S16-frontend-web-ui-patch/` | adds the only intrinsically browser-required semantic role bundle |
| `P05` | `S17` | `R17 $qt-ui-engineer` | `Scenarios-v2/S17-qt-desktop-ui-patch/` | adds the missing Qt specialty implementation bundle |
| `P06` | `S25` | `R25 $qa-engineer` | `Scenarios-v2/S25-qa-verification-verdict/` | adds the semantic QA report-and-verdict bundle before broader reruns |
| `P07` | `S33` | `A02 $external-reviewer` | `Scenarios-v2/S33-external-reviewer-transport-fidelity/` | completes the adapter pair while keeping transport evidence separate from semantic review evidence |

## Wave-wide rules

| Rule | Requirement |
|---|---|
| write boundary | this wave may add files only under the seven planned second-wave roots in `Scenarios-v2/` |
| protected first-wave surfaces | do not edit `Scenarios-v2/S02-lead-recovery-packet/`, `S07-architect-multi-seam-adr/`, `S12-security-trust-boundary-package/`, `S21-toolchain-ownership-patch/`, `S22-geometry-predicate-patch/`, `S26-architecture-review-findings/`, or `S32-external-worker-transport-fidelity/` |
| protected planning surfaces | do not edit `Work/next-upgraded-pack/Planning/next-phase/*.md`, including the accepted redesign stack and the first-wave materialization plan |
| protected evidence surfaces | do not edit `Work/next-upgraded-pack/Checkpoints/**`, `Work/next-upgraded-pack/Evidence/**`, or `Work/next-upgraded-pack/Results-drafts/**` in this wave |
| protected legacy surfaces | do not edit `Work/next-upgraded-pack/Fixtures/**`, `Work/next-upgraded-pack/Tooling/**`, or `Archive/**`; legacy upgraded-pack semantics remain archive-only reference material |
| bundle contract | every admitted root must contain `scenario.yaml`, `README.md`, `inputs/`, `candidate/`, `oracle/`, and `verifiers/` |
| identity discipline | v2 bundle metadata must use `Snn`, `Rnn`, `Ann`, and `Pnn` only; old `T/L/O` naming may appear only as reference notes inside bundle-local materials |
| browser overlay discipline | only `S16` may declare `overlay_flags: [browser-required]`; no other second-wave root may require browser execution |
| memo and review discipline | `S03`, `S06`, and `S10` stay memo-only; `S25` stays QA-report-only; none of those roots may embed implementation work as the editable candidate surface |
| adapter separation | `S33` stays adapter-only and transport-only; it must not be usable as semantic review or QA evidence |
| no reruns yet | no provider rerun, scoring update, ranking update, or publication-table rewrite is part of this wave |
| no task-memory expansion | do not create `work-items/` scaffolding or other repo task-memory additions as part of this plan |

## Phase order

`Phase 1` is the narrowest second-wave addition and anchors the advisory memo pattern before the
remaining memo, implementation, review, and adapter bundles are added.

After `Phase 1` passes:

- `Phases 2-3` are independent memo-only sibling-root additions and may run in parallel because
  their write surfaces do not overlap and their contracts are already fixed by the accepted docs.
- `Phases 4-5` are independent implementation-root additions and may run in parallel after
  `Phases 2-3 PASS`, because the browser-vs-Qt boundary is then explicit and their write surfaces
  remain disjoint.
- `Phase 6` stays after the implementation roots so the semantic QA bundle can inherit the now-live
  second-wave implementation conventions without redefining them.
- `Phase 7` stays last so the external-reviewer transport bundle can mirror the review-side report
  contract without becoming semantic review evidence.

## Phase 1 - Materialize `P01 / S03`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S03-consultant-tradeoff-memo/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | accepted second-wave planning inputs and the existing first-wave roots as reference only; no prior second-wave phase |
| allowed change surface | `Scenarios-v2/S03-consultant-tradeoff-memo/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, especially the accepted `S02` root and the first-wave pack/separation contract |
| checks | confirm `scenario.yaml` matches `S03`, `R03`, `P01`, `advisory`, `advisory memo`, the shared owner/advisory/factual/design/planning score profile, and `overlay_flags: []`; confirm the candidate surface is a single advisory memo only; confirm inputs describe incomplete but non-empty evidence and a real tradeoff question; confirm oracle and verifiers enforce advisory-only behavior, explicit uncertainty, and no hidden routing or approval authority |
| acceptance criteria | `S03` clearly benchmarks consultant-style second-opinion behavior rather than lead orchestration, reviewer gating, or implementation work; the bundle is self-contained and aligned with the accepted pack specs |
| rollback notes | delete only `Scenarios-v2/S03-consultant-tradeoff-memo/` |

## Phase 2 - Materialize `P02 / S06`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S06-analyst-repository-fact-memo/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | `Phase 1 PASS` |
| allowed change surface | `Scenarios-v2/S06-analyst-repository-fact-memo/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, the accepted first-wave roots, and the accepted `S03` root |
| checks | confirm `scenario.yaml` matches `S06`, `R06`, `P02`, `factual`, `factual research memo`, the shared owner/advisory/factual/design/planning score profile, and `overlay_flags: []`; confirm inputs include repository facts plus decoys or false leads; confirm the candidate surface is one factual research memo only; confirm oracle and verifiers require file references, explicit unknown-vs-confirmed boundaries, and rejection of design, planning, or implementation drift |
| acceptance criteria | `S06` clearly benchmarks repository fact extraction with decoy pressure and does not collapse into architecture recommendations, phased delivery planning, or consultant-style advice |
| rollback notes | delete only `Scenarios-v2/S06-analyst-repository-fact-memo/` |

## Phase 3 - Materialize `P03 / S10`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S10-algorithm-invariant-proof-memo/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | `Phase 1 PASS` |
| allowed change surface | `Scenarios-v2/S10-algorithm-invariant-proof-memo/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, the accepted first-wave roots, and the accepted `S03` root |
| checks | confirm `scenario.yaml` matches `S10`, `R10`, `P03`, `scientist`, `invariant and proof memo`, the `scientist, constraints` score profile, and `overlay_flags: []`; confirm the bundle remains non-web and evidence-heavy; confirm inputs, oracle, and verifiers require a formal problem statement, explicit invariants, viable alternatives, complexity tradeoffs, and failure-mode or edge-case reasoning; confirm the candidate surface is memo-only and contains no production code |
| acceptance criteria | `S10` clearly benchmarks formal algorithm framing rather than generic design prose, computational-scientist modeling, or constraint-package policy writing; the bundle remains self-contained and role-correct for `P03` |
| rollback notes | delete only `Scenarios-v2/S10-algorithm-invariant-proof-memo/` |

## Phase 4 - Materialize `P04 / S16`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S16-frontend-web-ui-patch/**` |
| file scope | one new sibling root with the required six top-level bundle entries and a bundle-local browser-capable candidate subtree only |
| recommended materialization owner | `$frontend-engineer` |
| dependencies | `Phases 2-3 PASS` |
| allowed change surface | `Scenarios-v2/S16-frontend-web-ui-patch/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted first-wave roots, and the accepted second-wave memo roots |
| checks | confirm `scenario.yaml` matches `S16`, `R16`, `P04`, `implementation`, `code patch plus local verification`, `web UI`, the `implementation` score profile, and `overlay_flags: [browser-required]`; confirm the candidate surface stays inside bundle-local web UI files and direct browser verification material only; confirm inputs, oracle, and verifiers cover user-visible UI states, accessibility-sensitive labels or states, and local verification expectations; confirm the bundle does not drift into Qt, backend, platform, or scorer-edit semantics |
| acceptance criteria | `S16` is the only intrinsically browser-required semantic root in the wave, is clearly web-specific, and remains a bounded implementation bundle rather than a generic multi-surface patch |
| rollback notes | delete only `Scenarios-v2/S16-frontend-web-ui-patch/` |

## Phase 5 - Materialize `P05 / S17`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S17-qt-desktop-ui-patch/**` |
| file scope | one new sibling root with the required six top-level bundle entries and a bundle-local Qt candidate subtree only |
| recommended materialization owner | `$qt-ui-engineer` |
| dependencies | `Phases 2-3 PASS` |
| allowed change surface | `Scenarios-v2/S17-qt-desktop-ui-patch/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted first-wave roots, and the accepted second-wave memo roots |
| checks | confirm `scenario.yaml` matches `S17`, `R17`, `P05`, `implementation`, `code patch plus local verification`, `Qt desktop UI`, the `implementation` score profile, and `overlay_flags: []`; confirm the candidate surface stays inside bundle-local Qt widgets, dialogs, and direct UI verification material only; confirm inputs, oracle, and verifiers encode focus behavior, keyboard behavior, widget lifecycle, and explicit non-browser expectations; confirm the bundle does not drift into frontend web, model-view, geometry, or scorer-edit semantics |
| acceptance criteria | `S17` stays distinctly Qt-specific, non-web, and role-correct for the specialty implementation pack; it cannot be mistaken for `S16` with desktop wording added later |
| rollback notes | delete only `Scenarios-v2/S17-qt-desktop-ui-patch/` |

## Phase 6 - Materialize `P06 / S25`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S25-qa-verification-verdict/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$qa-engineer` |
| dependencies | `Phases 4-5 PASS` |
| allowed change surface | `Scenarios-v2/S25-qa-verification-verdict/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted first-wave roots, and all previously accepted second-wave roots |
| checks | confirm `scenario.yaml` matches `S25`, `R25`, `P06`, `review`, `QA report and test verdict`, `verification and test design`, the `review, QA` score profile, and `overlay_flags: []`; confirm the candidate surface is a QA report or verdict only; confirm inputs, oracle, and verifiers encode acceptance-criteria mapping, nearby smoke coverage, regression classification, and bug-registry expectations; confirm the bundle does not embed code patching, architecture redesign, or transport-provenance scoring as the editable surface |
| acceptance criteria | `S25` clearly benchmarks evidence-backed QA verification and verdict writing, not architecture review, UX review, or implementation repair work; review-only separation remains intact |
| rollback notes | delete only `Scenarios-v2/S25-qa-verification-verdict/` |

## Phase 7 - Materialize `P07 / S33`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S33-external-reviewer-transport-fidelity/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$platform-engineer` |
| dependencies | `Phase 6 PASS` |
| allowed change surface | `Scenarios-v2/S33-external-reviewer-transport-fidelity/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted first-wave roots, all accepted second-wave semantic roots, and the adapter-only separation already established by `S32` |
| checks | confirm `scenario.yaml` matches `S33`, `A02`, `P07`, `adapter`, `transport execution report`, `transport fidelity`, the `adapters` score profile, and `overlay_flags: [external-transport]`; confirm the candidate surface is one adapter report only; confirm inputs, oracle, and verifiers require external-reviewer provenance fields, explicit review strategy handling, and fail-closed transport behavior; confirm no semantic reviewer findings, QA verdict substitution, provider ranking, or hidden internal fallback behavior is embedded in the bundle |
| acceptance criteria | `S33` remains transport-only, adapter-only, and clearly separate from semantic review or QA evidence; it complements `S32` without redefining the semantic review packs |
| rollback notes | delete only `Scenarios-v2/S33-external-reviewer-transport-fidelity/` |

## Integration owner and wave gate

| Item | Requirement |
|---|---|
| integration owner | `$knowledge-archivist` |
| integration responsibilities | assemble the seven admitted second-wave roots into the existing `Scenarios-v2/` tree; confirm the exact admitted set added by this wave is `S03`, `S06`, `S10`, `S16`, `S17`, `S25`, and `S33`; confirm the accepted first-wave roots remain unchanged; confirm every new metadata row still matches `scenario-backlog-v1`, `pack-specs-v1`, and `scoring-and-results-model`; confirm `S16` is the only second-wave root with `browser-required`; confirm `S25` remains semantic QA evidence while `S33` remains adapter-only transport evidence; confirm no protected surfaces changed |
| mandatory QA gate | `$qa-engineer` must verify required bundle structure, metadata alignment, local verifier presence and execution, diff isolation, and the browser-vs-Qt modality split before any second-wave root is treated as v2-ready |
| mandatory review gate | `$architecture-reviewer` must verify pack cohesion, advisory/factual/scientist/implementation/review/adapter separation, browser-vs-Qt boundary integrity, adapter isolation, and absence of taxonomy or scoring drift before any second-wave root is treated as v2 evidence |
| non-mandatory conditional gate | add `$ui-test-engineer` only if `S16` or `S17` widens into screenshot baselines, live UI runners, or visual-fixture maintenance beyond bundle-local verifiers |
| whole-wave rollback | because the wave is additive-only, rollback is bundle-by-bundle deletion of the seven second-wave roots under `Scenarios-v2/`; do not compensate by editing first-wave roots, accepted planning docs, evidence docs, checkpoints, or legacy fixture/archive surfaces |

## Recommended next role sequence

1. `$lead` accepts this plan and routes `Phase 1`.
2. `$knowledge-archivist` materializes `Phase 1` and remains the integration owner throughout the wave.
3. `$knowledge-archivist` materializes `Phases 2-3`.
4. `$frontend-engineer` materializes `Phase 4`.
5. `$qt-ui-engineer` materializes `Phase 5`.
6. `$qa-engineer` materializes `Phase 6`.
7. `$platform-engineer` materializes `Phase 7`.
8. `$knowledge-archivist` performs the integration pass and hands the complete expanded `Scenarios-v2/` tree to verification.
9. `$qa-engineer` performs the mandatory wave gate.
10. `$architecture-reviewer` performs the mandatory pre-evidence review.
11. `$ui-test-engineer` runs only if the conditional UI gate is triggered by the materialized bundle contents.

## Gate decision

`PASS` - the lead can accept the second-wave materialization plan and route the first second-wave
implementation phase without reopening taxonomy, first-wave decisions, or score-profile mapping.

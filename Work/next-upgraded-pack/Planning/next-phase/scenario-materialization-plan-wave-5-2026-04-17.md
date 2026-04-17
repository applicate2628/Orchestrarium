Date: 2026-04-17
Owner: `$planner`
Status: `PASS`

## Purpose

This plan turns the admitted final-wave scenario set into real v2 bundle roots under
`Scenarios-v2/` without reopening the accepted redesign stack, the completed first-wave through
fourth-wave roots, the completed adapter pair, scoring rules, or provider execution policy.

The admitted set below is derived from:

- `scenario-backlog-v1-2026-04-17.md`
- `pack-specs-v1-2026-04-17.md`
- `scoring-and-results-model-2026-04-17.md`
- `scenario-materialization-plan-wave-4-2026-04-17.md`
- `status-2026-04-16.md`
- the current `Scenarios-v2/` tree

This final wave stays balanced by closure rather than by one-per-pack symmetry:

- admit exactly the remaining unmaterialized semantic roots and no others
- write only under new sibling roots in `Scenarios-v2/`
- treat the twenty-six completed roots plus the adapter pair as reference-only, not mutable surfaces
- stop before provider reruns, scoring updates, result-table rewrites, or checkpoint changes
- close milestone-1 role-complete materialization so `S01..S33` all exist after this wave

All paths below are relative to the benchmarks worktree root `D:/dev/Orchestrator/benchmarks/`.

## Admitted final-wave set

| Pack | Scenario | Surface | Planned root | Reason for admission |
|---|---|---|---|---|
| `P02` | `S05` | `R05 $product-analyst` | `Scenarios-v2/S05-product-analyst-brief/` | closes the last factual product-framing modality and completes `P02` |
| `P03` | `S14` | `R14 $reliability-engineer` | `Scenarios-v2/S14-reliability-rollout-package/` | closes the last scientist-constraints lane with rollout, failure-mode, and rollback pressure |
| `P04` | `S15` | `R15 $backend-engineer` | `Scenarios-v2/S15-backend-owner-seam-patch/` | closes the missing backend owner-seam implementation modality in `P04` |
| `P05` | `S18` | `R18 $model-view-engineer` | `Scenarios-v2/S18-model-view-correctness-patch/` | closes the remaining Qt model/view correctness lane and pairs cleanly with `S17` |
| `P06` | `S27` | `R27 $security-reviewer` | `Scenarios-v2/S27-security-review-findings/` | closes the security-review findings lane paired to `S12` |
| `P06` | `S28` | `R28 $performance-reviewer` | `Scenarios-v2/S28-performance-review-findings/` | closes the performance-review findings lane paired to `S13` |
| `P06` | `S30` | `R30 $ux-reviewer` | `Scenarios-v2/S30-ux-review-findings/` | closes the UX-review findings lane paired to `S08` |

## Closure consequence

After this wave passes:

| Check | Read |
|---|---|
| semantic coverage | all `R01..R31` will have materialized `Scenarios-v2` roots |
| adapter coverage | `S32` and `S33` remain complete and untouched |
| total v2 roots | `33` |
| deferred remainder | none |

## Wave-wide rules

| Rule | Requirement |
|---|---|
| write boundary | this wave may add files only under the seven planned final-wave roots in `Scenarios-v2/` |
| protected existing scenario roots | do not edit any already-materialized root in `Scenarios-v2/`; every current root outside `S05`, `S14`, `S15`, `S18`, `S27`, `S28`, and `S30` is protected |
| protected planning surfaces | do not edit `Work/next-upgraded-pack/Planning/next-phase/*.md`, including the accepted redesign stack and prior wave plans |
| protected evidence surfaces | do not edit `Work/next-upgraded-pack/Checkpoints/**`, `Work/next-upgraded-pack/Evidence/**`, or `Work/next-upgraded-pack/Results-drafts/**` in this wave |
| protected legacy surfaces | do not edit `Work/next-upgraded-pack/Fixtures/**`, `Work/next-upgraded-pack/Tooling/**`, or `Archive/**`; old upgraded-pack assets remain reference-only |
| bundle contract | every admitted root must contain `scenario.yaml`, `README.md`, `inputs/`, `candidate/`, `oracle/`, and `verifiers/` |
| identity discipline | v2 bundle metadata must use `Snn`, `Rnn`, and `Pnn` only; old `T/L/O` naming may appear only as reference notes inside bundle-local materials |
| overlay discipline | all admitted final-wave roots must keep `overlay_flags: []` |
| packet discipline | `S05` and `S14` stay memo or packet-only; neither may embed implementation work, review findings, or transport evidence as the editable candidate surface |
| implementation discipline | only `S15` and `S18` may contain code-bearing candidate trees; both must stay bundle-local and must not reopen shared runners, results surfaces, or existing scenario roots |
| review discipline | `S27`, `S28`, and `S30` stay findings-only review bundles; none may become implementation patches, QA verdicts, or adapter reports |
| adapter closure | `S32` and `S33` are already complete; no final-wave root may reuse adapter transport evidence as semantic role evidence or reopen the adapter lane |
| no reruns yet | no provider rerun, scoring update, ranking update, or publication-table rewrite is part of this wave |
| no task-memory expansion | do not create `work-items/` scaffolding or other repo task-memory additions as part of this plan |

## Phase order

`Phase 1` anchors the wave with the remaining product-brief packet because it closes the last
product-facing factual bundle and gives the final wave a clean document-first start.

After `Phase 1` passes:

- `Phase 2` closes the last constraint packet and completes the packet-only remainder.
- `Phases 3-4` are independent implementation-root additions and may run in parallel after
  `Phases 1-2 PASS`, because the document-first conventions are fixed and the two candidate trees
  stay in separate general-vs-specialty implementation packs.
- `Phases 5-7` are independent review-only additions and may run in parallel after `Phases 3-4 PASS`,
  because the remaining review roots can then inherit the now-complete implementation-modality set
  without widening into patches.
- integration starts only after all seven admitted roots are present, followed by the mandatory
  `integration -> QA -> architecture-review` gate chain.

## Phase 1 - Materialize `P02 / S05`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S05-product-analyst-brief/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | accepted final-wave planning inputs and the existing twenty-six roots as reference only; no prior final-wave phase |
| allowed change surface | `Scenarios-v2/S05-product-analyst-brief/**` only |
| must-not-break surfaces | all wave-wide protected surfaces and the no-edit rule for all existing scenario roots |
| checks | confirm `scenario.yaml` matches `S05`, `R05`, `P02`, `factual`, `product brief`, `product framing`, the shared owner, advisory, factual, design, planning score profile, and `overlay_flags: []`; confirm the candidate surface is one product brief only; confirm inputs, oracle, and verifiers encode noisy intake notes, explicit product constraints, open questions, and prohibition on architecture, planning, or implementation drift |
| acceptance criteria | `S05` clearly benchmarks factual product framing rather than roadmap ownership, architecture design, or phased delivery planning; the bundle is self-contained and aligned with the accepted pack specs |
| rollback notes | delete only `Scenarios-v2/S05-product-analyst-brief/` |

## Phase 2 - Materialize `P03 / S14`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S14-reliability-rollout-package/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | `Phase 1 PASS` |
| allowed change surface | `Scenarios-v2/S14-reliability-rollout-package/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted `S05` root |
| checks | confirm `scenario.yaml` matches `S14`, `R14`, `P03`, `constraint`, `reliability constraint package`, `failure and rollout analysis`, the `scientist, constraints` score profile, and `overlay_flags: []`; confirm the bundle stays non-web and packet-only; confirm inputs, oracle, and verifiers require rollout sequencing, failure modes, rollback conditions, degradation expectations, and observability or recovery anchors without drifting into implementation repair or review findings |
| acceptance criteria | `S14` clearly benchmarks reliability constraints rather than platform ownership, performance analysis, or security threat modeling; the bundle stays evidence-heavy and role-correct for `P03` |
| rollback notes | delete only `Scenarios-v2/S14-reliability-rollout-package/` |

## Phase 3 - Materialize `P04 / S15`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S15-backend-owner-seam-patch/**` |
| file scope | one new sibling root with the required six top-level bundle entries and a bundle-local backend workspace only |
| recommended materialization owner | `$backend-engineer` |
| dependencies | `Phases 1-2 PASS` |
| allowed change surface | `Scenarios-v2/S15-backend-owner-seam-patch/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted packet roots `S05` and `S14` |
| checks | confirm `scenario.yaml` matches `S15`, `R15`, `P04`, `implementation`, `code patch plus local verification`, `backend code`, the `implementation` score profile, and `overlay_flags: []`; confirm the candidate surface stays inside a bundle-local backend-owned seam and direct validation path only; confirm inputs, oracle, and verifiers encode owner-seam discipline, contract expectations, and forbidden widening into platform, data, toolchain, or result-surface edits |
| acceptance criteria | `S15` adds the missing backend implementation modality, stays distinct from the already-complete data, platform, toolchain, and web roots, and remains a bounded code-patch bundle |
| rollback notes | delete only `Scenarios-v2/S15-backend-owner-seam-patch/` |

## Phase 4 - Materialize `P05 / S18`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S18-model-view-correctness-patch/**` |
| file scope | one new sibling root with the required six top-level bundle entries and a bundle-local Qt model/view workspace only |
| recommended materialization owner | `$model-view-engineer` |
| dependencies | `Phases 1-2 PASS` |
| allowed change surface | `Scenarios-v2/S18-model-view-correctness-patch/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted packet roots `S05` and `S14` |
| checks | confirm `scenario.yaml` matches `S18`, `R18`, `P05`, `implementation`, `code patch plus local verification`, `Qt model/view`, the `implementation` score profile, and `overlay_flags: []`; confirm the candidate surface stays inside a bundle-local model/view seam and direct validation path only; confirm inputs, oracle, and verifiers encode delegate or model correctness, selection or indexing behavior, proxy or update semantics, and explicit boundaries against Qt UI, graphics, visualization, or scorer drift |
| acceptance criteria | `S18` adds the missing model/view correctness lane, stays distinctly separate from `S17`, `S22`, `S23`, and `S24`, and preserves the non-web specialty boundary of `P05` |
| rollback notes | delete only `Scenarios-v2/S18-model-view-correctness-patch/` |

## Phase 5 - Materialize `P06 / S27`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S27-security-review-findings/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$security-reviewer` |
| dependencies | `Phases 3-4 PASS` |
| allowed change surface | `Scenarios-v2/S27-security-review-findings/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and all previously accepted final-wave roots |
| checks | confirm `scenario.yaml` matches `S27`, `R27`, `P06`, `review`, `review findings`, `security gate`, the `review, QA` score profile, and `overlay_flags: []`; confirm the candidate surface is a findings-only security report; confirm inputs, oracle, and verifiers encode trust boundaries, secret handling, auth or data exposure risks, severity anchors, and false-positive traps without turning the root into a security-engineer constraint package or a patch root |
| acceptance criteria | `S27` clearly benchmarks security-review findings rather than threat-model design or implementation repair; review-only separation remains intact |
| rollback notes | delete only `Scenarios-v2/S27-security-review-findings/` |

## Phase 6 - Materialize `P06 / S28`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S28-performance-review-findings/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$performance-reviewer` |
| dependencies | `Phases 3-4 PASS` |
| allowed change surface | `Scenarios-v2/S28-performance-review-findings/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and all previously accepted final-wave roots |
| checks | confirm `scenario.yaml` matches `S28`, `R28`, `P06`, `review`, `review findings`, `performance gate`, the `review, QA` score profile, and `overlay_flags: []`; confirm the candidate surface is a findings-only performance report; confirm inputs, oracle, and verifiers encode budgets, bottleneck claims, measurement evidence, severity anchors, and false-positive traps without turning the root into a performance-engineer constraint package or an implementation patch |
| acceptance criteria | `S28` clearly benchmarks performance-review findings rather than performance-constraint definition or code optimization work; review-only separation remains intact |
| rollback notes | delete only `Scenarios-v2/S28-performance-review-findings/` |

## Phase 7 - Materialize `P06 / S30`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S30-ux-review-findings/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$ux-reviewer` |
| dependencies | `Phases 3-4 PASS` |
| allowed change surface | `Scenarios-v2/S30-ux-review-findings/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and all previously accepted final-wave roots |
| checks | confirm `scenario.yaml` matches `S30`, `R30`, `P06`, `review`, `review findings`, `UX gate`, the `review, QA` score profile, and `overlay_flags: []`; confirm the candidate surface is a findings-only UX review report; confirm inputs, oracle, and verifiers encode flow clarity, interaction comprehension, content hierarchy, severity anchors, and false-positive traps without turning the root into a UX-design brief, QA verdict, or implementation patch |
| acceptance criteria | `S30` clearly benchmarks UX-review findings rather than pre-implementation UX design or UI repair work; review-only separation remains intact |
| rollback notes | delete only `Scenarios-v2/S30-ux-review-findings/` |

## Integration owner and wave gate

| Item | Requirement |
|---|---|
| integration owner | `$knowledge-archivist` |
| integration responsibilities | assemble the seven admitted final-wave roots into the existing `Scenarios-v2/` tree; confirm the exact admitted set added by this wave is `S05`, `S14`, `S15`, `S18`, `S27`, `S28`, and `S30`; confirm all twenty-six previously completed roots remain unchanged; confirm every new metadata row still matches `scenario-backlog-v1`, `pack-specs-v1`, and `scoring-and-results-model`; confirm all seven new roots keep `overlay_flags: []`; confirm the completed adapter pair remains untouched; confirm no provider rerun or result-table rewrite was introduced |
| mandatory integration gate | integration must finish before QA starts; the integration memo must treat the existing twenty-six roots and the adapter pair as protected reference-only scope for this wave |
| mandatory QA gate | `$qa-engineer` must verify required bundle structure, metadata alignment, local verifier presence or execution, diff isolation, packet-vs-implementation-vs-review separation, and the findings-only discipline of `S27`, `S28`, and `S30` before any final-wave root is treated as v2-ready |
| mandatory review gate | `$architecture-reviewer` must verify pack cohesion, product-vs-reliability-vs-implementation-vs-review separation, backend-vs-model-view boundary integrity, protected-root isolation, and absence of taxonomy or scoring drift before any final-wave root is treated as v2 evidence |
| non-mandatory conditional gate | add `$ui-test-engineer` only if `S18` or `S30` widens into screenshot baselines, live UI runners, or visual-fixture maintenance beyond bundle-local verifiers |
| whole-wave rollback | because the wave is additive-only, rollback is bundle-by-bundle deletion of the seven final-wave roots under `Scenarios-v2/`; do not compensate by editing existing scenario roots, accepted planning docs, evidence docs, checkpoints, results drafts, or legacy fixture or archive surfaces |

## Recommended next role sequence

1. `$lead` accepts this plan and routes `Phase 1`.
2. `$knowledge-archivist` materializes `Phase 1`.
3. `$knowledge-archivist` materializes `Phase 2` and remains the integration owner throughout the wave.
4. `$backend-engineer` materializes `Phase 3`.
5. `$model-view-engineer` materializes `Phase 4`.
6. `$security-reviewer` materializes `Phase 5`.
7. `$performance-reviewer` materializes `Phase 6`.
8. `$ux-reviewer` materializes `Phase 7`.
9. `$knowledge-archivist` performs the mandatory integration pass and hands the completed `Scenarios-v2/` tree to verification.
10. `$qa-engineer` performs the mandatory wave gate.
11. `$architecture-reviewer` performs the mandatory pre-evidence review.
12. `$ui-test-engineer` runs only if the conditional UI gate is triggered by the materialized bundle contents.

## Gate decision

`PASS` - the final-wave materialization plan is execution-ready, preserves the accepted additive
scope discipline, closes the exact remaining v2 semantic roots, and completes milestone-1
role-complete `Scenarios-v2` coverage without reopening prior-wave or adapter surfaces.

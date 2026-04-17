Date: 2026-04-17
Owner: `$planner`
Status: `PASS`

## Purpose

This plan turns the admitted fourth-wave scenario set into real v2 bundle roots under
`Scenarios-v2/` without reopening the accepted redesign stack, the completed first-wave through
third-wave roots, the completed adapter lane, scoring rules, provider execution policy, or current
results surfaces.

The admitted set below is derived from:

- `Work/next-upgraded-pack/Checkpoints/status-2026-04-16.md`
- `Work/next-upgraded-pack/Planning/next-phase/scenario-backlog-v1-2026-04-17.md`
- `Work/next-upgraded-pack/Planning/next-phase/benchmark-architecture-v2-2026-04-17.md`
- `Work/next-upgraded-pack/Planning/next-phase/pack-specs-v1-2026-04-17.md`
- `Work/next-upgraded-pack/Planning/next-phase/scoring-and-results-model-2026-04-17.md`
- `Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md`
- `Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-3-2026-04-17.md`

The admitted wave stays balanced by design:

- create exactly one new real bundle from each remaining non-adapter pack `P01..P06`
- write only under new sibling roots in `Scenarios-v2/`
- treat the twenty completed scenario roots as reference-only, not mutable surfaces
- stop before provider reruns, scoring updates, result-table rewrites, or checkpoint changes
- prefer the most modality-distinct remaining surface in each pack so the later remainder becomes a
  coherent paired-follow-up wave rather than a second mixed grab-bag

All paths below are relative to the benchmarks worktree root `D:/dev/Orchestrator/benchmarks/`.

## Admitted bundle set

| Pack | Scenario | Surface | Planned root | Reason for admission |
|---|---|---|---|---|
| `P01` | `S01` | `R01 $product-manager` | `Scenarios-v2/S01-product-manager-roadmap-prioritization/` | closes the last owner surface with the missing roadmap-and-intake decision modality |
| `P02` | `S08` | `R08 $ux-designer` | `Scenarios-v2/S08-ux-designer-mixed-surface-brief/` | adds the missing UX-structure design modality and broadens `P02` beyond factual or architecture-only memo work |
| `P03` | `S13` | `R13 $performance-engineer` | `Scenarios-v2/S13-performance-engineer-bottleneck-budget-package/` | adds the remaining performance-constraint lane and leaves the paired performance-review gate for a later wave |
| `P04` | `S20` | `R20 $platform-engineer` | `Scenarios-v2/S20-platform-engineer-observability-patch/` | adds the missing config-and-validation implementation modality that current general implementation roots do not yet cover |
| `P05` | `S24` | `R24 $visualization-engineer` | `Scenarios-v2/S24-visualization-engineer-interpretation-patch/` | adds the missing visualization-semantics implementation lane that `S23` already fences as separate future work |
| `P06` | `S31` | `R31 $ui-test-engineer` | `Scenarios-v2/S31-ui-test-engineer-regression-report/` | adds the last review-pack artifact shape not yet materialized: UI-regression verification as a report rather than findings or a QA verdict |

## Deferred paired-follow-up remainder

The admitted fourth-wave set intentionally leaves a smaller seven-root remainder for one later wave.
That remainder is more coherent after the fourth-wave surfaces above exist:

| Deferred scenario | Deferred reason |
|---|---|
| `S05` | remains the product-brief follow-up to `S01`, so the final wave can close the product-facing memo pair cleanly instead of spending two product-facing slots in one wave |
| `S14` | remains the rollout, failure-mode, and rollback follow-up to the newly admitted platform lane `S20` |
| `S15` | remains the last general implementation code-patch lane after the config-heavy platform lane is established |
| `S18` | remains the model/view follow-up to the already-live Qt root `S17`, which keeps the fourth-wave specialty pick focused on visualization rather than another Qt-adjacent root |
| `S27` | remains the security-review findings lane paired to the already-live security-engineer root `S12` |
| `S28` | remains the performance-review findings lane paired to the newly admitted performance-engineer root `S13` |
| `S30` | remains the UX-review findings lane paired to the newly admitted UX-design root `S08` |

## Wave-wide rules

| Rule | Requirement |
|---|---|
| write boundary | this wave may add files only under the six planned fourth-wave roots in `Scenarios-v2/` |
| protected existing scenario roots | do not edit `Scenarios-v2/S02-lead-recovery-packet/`, `S03-consultant-tradeoff-memo/`, `S04-knowledge-archivist-source-of-truth-update/`, `S06-analyst-repository-fact-memo/`, `S07-architect-multi-seam-adr/`, `S09-planner-phased-delivery-plan/`, `S10-algorithm-invariant-proof-memo/`, `S11-computational-scientist-model-validation-memo/`, `S12-security-trust-boundary-package/`, `S16-frontend-web-ui-patch/`, `S17-qt-desktop-ui-patch/`, `S19-data-engineer-pipeline-patch/`, `S21-toolchain-ownership-patch/`, `S22-geometry-predicate-patch/`, `S23-graphics-engineer-rendering-patch/`, `S25-qa-verification-verdict/`, `S26-architecture-review-findings/`, `S29-accessibility-review-findings/`, `S32-external-worker-transport-fidelity/`, or `S33-external-reviewer-transport-fidelity/` |
| protected planning surfaces | do not edit `Work/next-upgraded-pack/Planning/next-phase/*.md`, including the accepted redesign stack, the prior wave plans, or the backlog and scoring docs |
| protected evidence surfaces | do not edit `Work/next-upgraded-pack/Checkpoints/**`, `Work/next-upgraded-pack/Evidence/**`, or `Work/next-upgraded-pack/Results-drafts/**` in this wave |
| protected legacy surfaces | do not edit `Work/next-upgraded-pack/Fixtures/**`, `Work/next-upgraded-pack/Tooling/**`, or `Archive/**`; old upgraded-pack assets remain reference-only |
| bundle contract | every admitted root must contain `scenario.yaml`, `README.md`, `inputs/`, `candidate/`, `oracle/`, and `verifiers/` |
| identity discipline | v2 bundle metadata must use `Snn`, `Rnn`, and `Pnn` only; old `Tnn`, `Lnn`, `Onn`, or adapter IDs may appear only as reference notes inside bundle-local materials |
| overlay discipline | all admitted fourth-wave roots must keep `overlay_flags: []`; this wave must not introduce new `browser-required` or `external-transport` roots |
| packet discipline | `S01`, `S08`, and `S13` stay memo or packet-only; none may embed implementation work, review findings, or transport scoring as the editable candidate surface |
| implementation discipline | only `S20` and `S24` may contain code- or config-bearing candidate trees; they must stay bundle-local and must not reopen shared tooling, runners, results surfaces, or existing scenario roots |
| review discipline | `S31` stays report-only and verification-only; it must not mutate the reviewed UI target, become a QA-verdict substitute, or widen into an accessibility or UX-review findings bundle |
| adapter closure | `S32` and `S33` are already complete; no fourth-wave root may reuse adapter transport evidence as semantic role evidence or reopen the adapter lane |
| no reruns yet | no provider rerun, scoring update, ranking update, or result-table rewrite is part of this wave |
| no task-memory expansion | do not create `work-items/` scaffolding or other repo task-memory additions as part of this plan |

## Phase order

`Phase 1` anchors the wave with the missing roadmap-and-intake owner packet because it sets the
last unmaterialized `P01` contract before the rest of the mixed document, implementation, and
review surfaces are added.

After `Phase 1` passes:

- `Phases 2-3` are independent memo or packet additions and may run in parallel because their
  write surfaces do not overlap and their contracts are fixed by the accepted docs.
- `Phases 4-5` are independent implementation-root additions and may run in parallel after
  `Phases 2-3 PASS`, because the document-first conventions are then stable and the two candidate
  trees stay in separate general-vs-specialty implementation packs.
- `Phase 6` stays after the implementation roots so the UI-test bundle can inherit live
  verification conventions without reopening the existing frontend, Qt, or accessibility roots.
- integration starts only after all six admitted roots are present, followed by the mandatory
  `integration -> QA -> architecture-review` gate chain.

## Phase 1 - Materialize `P01 / S01`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S01-product-manager-roadmap-prioritization/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | accepted fourth-wave planning inputs and the existing twenty roots as reference only; no prior fourth-wave phase |
| allowed change surface | `Scenarios-v2/S01-product-manager-roadmap-prioritization/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, especially the no-edit rule for all existing scenario roots |
| checks | confirm `scenario.yaml` matches `S01`, `R01`, `P01`, `owner`, `roadmap decision package`, `roadmap and intake`, the shared `owner, advisory, factual, design, planning` score profile, and `overlay_flags: []`; confirm the candidate surface is a roadmap decision package only; confirm inputs, oracle, and verifiers require explicit prioritization under conflicting product constraints and prohibit lead-orchestration recovery or implementation work as the artifact |
| acceptance criteria | `S01` clearly benchmarks roadmap ownership and prioritization rather than product analysis, lead routing, consultant tradeoff advice, or design synthesis; the bundle is self-contained and aligned with the accepted pack specs |
| rollback notes | delete only `Scenarios-v2/S01-product-manager-roadmap-prioritization/` |

## Phase 2 - Materialize `P02 / S08`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S08-ux-designer-mixed-surface-brief/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | `Phase 1 PASS` |
| allowed change surface | `Scenarios-v2/S08-ux-designer-mixed-surface-brief/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted `S01` root |
| checks | confirm `scenario.yaml` matches `S08`, `R08`, `P02`, `design`, `UX structure brief`, `interaction design`, the shared `owner, advisory, factual, design, planning` score profile, and `overlay_flags: []`; confirm the candidate surface is one UX brief only; confirm inputs, oracle, and verifiers encode a mixed desktop/web interaction problem, explicit state or flow restructuring, and the boundary between UX design vs implementation or review output |
| acceptance criteria | `S08` clearly benchmarks UX-design structure work rather than architecture ADR writing, web or Qt patching, or later UX-review findings; the root broadens `P02` without collapsing into generic product prose |
| rollback notes | delete only `Scenarios-v2/S08-ux-designer-mixed-surface-brief/` |

## Phase 3 - Materialize `P03 / S13`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S13-performance-engineer-bottleneck-budget-package/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | `Phase 1 PASS` |
| allowed change surface | `Scenarios-v2/S13-performance-engineer-bottleneck-budget-package/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted `S01` root |
| checks | confirm `scenario.yaml` matches `S13`, `R13`, `P03`, `constraint`, `performance constraint package`, `budget and bottleneck analysis`, the `scientist, constraints` score profile, and `overlay_flags: []`; confirm the bundle stays non-web and packet-only; confirm inputs, oracle, and verifiers require explicit budgets, bottleneck framing, measurement strategy, and tradeoff boundaries without drifting into implementation repair, review findings, or reliability-rollout policy |
| acceptance criteria | `S13` clearly benchmarks performance-constraint definition rather than generic optimization advice, platform ownership, or later performance-review findings; the bundle stays evidence-heavy and role-correct for `P03` |
| rollback notes | delete only `Scenarios-v2/S13-performance-engineer-bottleneck-budget-package/` |

## Phase 4 - Materialize `P04 / S20`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S20-platform-engineer-observability-patch/**` |
| file scope | one new sibling root with the required six top-level bundle entries and a bundle-local platform workspace only |
| recommended materialization owner | `$platform-engineer` |
| dependencies | `Phases 2-3 PASS` |
| allowed change surface | `Scenarios-v2/S20-platform-engineer-observability-patch/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted fourth-wave packet roots |
| checks | confirm `scenario.yaml` matches `S20`, `R20`, `P04`, `implementation`, `config patch plus validation`, `CI, deployment, or observability`, the `implementation` score profile, and `overlay_flags: []`; confirm the candidate surface stays inside a bundle-local platform-owned config or observability workspace and its direct validation route only; confirm inputs, oracle, and verifiers fence backend code, toolchain ownership, shared runners, provider routing, and results surfaces as out of scope |
| acceptance criteria | `S20` adds the missing platform implementation modality as a config-and-validation bundle, stays distinct from the already-complete data and toolchain roots, and does not reopen adapter or execution-runner surfaces |
| rollback notes | delete only `Scenarios-v2/S20-platform-engineer-observability-patch/` |

## Phase 5 - Materialize `P05 / S24`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S24-visualization-engineer-interpretation-patch/**` |
| file scope | one new sibling root with the required six top-level bundle entries and a bundle-local visualization workspace only |
| recommended materialization owner | `$visualization-engineer` |
| dependencies | `Phases 2-3 PASS` |
| allowed change surface | `Scenarios-v2/S24-visualization-engineer-interpretation-patch/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted fourth-wave packet roots |
| checks | confirm `scenario.yaml` matches `S24`, `R24`, `P05`, `implementation`, `code patch plus validation`, `scientific or data visualization`, the `implementation` score profile, and `overlay_flags: []`; confirm the candidate surface stays inside a visualization-owned bundle-local root and direct tests only; confirm inputs, oracle, and verifiers encode interpretation semantics, rendering or encoding expectations, and explicit boundaries against graphics-pipeline, Qt, model-view, or scorer drift |
| acceptance criteria | `S24` adds the missing visualization-semantics implementation lane, stays distinct from the already-complete graphics root `S23`, and preserves the non-web specialty boundary of `P05` |
| rollback notes | delete only `Scenarios-v2/S24-visualization-engineer-interpretation-patch/` |

## Phase 6 - Materialize `P06 / S31`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S31-ui-test-engineer-regression-report/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$ui-test-engineer` |
| dependencies | `Phases 4-5 PASS` |
| allowed change surface | `Scenarios-v2/S31-ui-test-engineer-regression-report/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and all previously accepted fourth-wave roots |
| checks | confirm `scenario.yaml` matches `S31`, `R31`, `P06`, `review`, `UI test report`, `UI regression verification`, the `review, QA` score profile, and `overlay_flags: []`; confirm the candidate surface is one regression report only; confirm inputs, oracle, and verifiers encode bundle-local UI evidence, regression expectations, and report-only discipline without turning the root into an implementation patch, a QA-verdict substitute, or a UX/accessibility findings bundle |
| acceptance criteria | `S31` clearly benchmarks UI-regression verification and report writing, not code repair, accessibility review, or UX-review findings; the fourth-wave review addition broadens `P06` with a new artifact shape rather than another findings-only lane |
| rollback notes | delete only `Scenarios-v2/S31-ui-test-engineer-regression-report/` |

## Integration owner and wave gate

| Item | Requirement |
|---|---|
| integration owner | `$knowledge-archivist` |
| integration responsibilities | assemble the six admitted fourth-wave roots into the existing `Scenarios-v2/` tree; confirm the exact admitted set added by this wave is `S01`, `S08`, `S13`, `S20`, `S24`, and `S31`; confirm all twenty previously completed roots remain unchanged; confirm every new metadata row still matches `scenario-backlog-v1`, `pack-specs-v1`, and `scoring-and-results-model`; confirm all six new roots keep `overlay_flags: []`; confirm the completed adapter pair remains untouched; confirm no provider rerun or result-table rewrite was introduced |
| mandatory integration gate | integration must finish before QA starts; the integration memo must treat the existing twenty roots and the seven deferred remainder surfaces as protected reference-only scope for this wave |
| mandatory QA gate | `$qa-engineer` must verify required bundle structure, metadata alignment, local verifier presence or execution, diff isolation, packet-vs-implementation-vs-review separation, and the report-vs-patch boundary for `S31` before any fourth-wave root is treated as v2-ready |
| mandatory review gate | `$architecture-reviewer` must verify pack cohesion, roadmap-vs-UX-design-vs-constraint-vs-implementation-vs-UI-test separation, platform-vs-visualization boundary integrity, protected-root isolation, and absence of taxonomy or scoring drift before any fourth-wave root is treated as v2 evidence |
| non-mandatory conditional gate | add `$accessibility-reviewer` only if `S24` or `S31` widens into accessibility-specific assertions or assistive-technology fixtures beyond the admitted bundle-local verification scope |
| whole-wave rollback | because the wave is additive-only, rollback is bundle-by-bundle deletion of the six fourth-wave roots under `Scenarios-v2/`; do not compensate by editing existing scenario roots, accepted planning docs, evidence docs, checkpoints, results drafts, or legacy fixture or archive surfaces |

## Recommended next role sequence

1. `$lead` accepts this plan and routes `Phase 1`.
2. `$knowledge-archivist` materializes `Phase 1` and remains the integration owner throughout the wave.
3. `$knowledge-archivist` materializes `Phases 2-3`.
4. `$platform-engineer` materializes `Phase 4`.
5. `$visualization-engineer` materializes `Phase 5`.
6. `$ui-test-engineer` materializes `Phase 6`.
7. `$knowledge-archivist` performs the mandatory integration pass and hands the expanded `Scenarios-v2/` tree to verification.
8. `$qa-engineer` performs the mandatory wave gate.
9. `$architecture-reviewer` performs the mandatory pre-evidence review.
10. `$accessibility-reviewer` runs only if the conditional verification gate is triggered by the materialized fourth-wave bundle contents.

## Gate decision

`PASS` - the fourth-wave materialization plan is execution-ready, preserves the accepted additive
scope discipline, maximizes distinct remaining modality coverage across `P01..P06`, and leaves a
coherent paired-follow-up remainder for one later wave.

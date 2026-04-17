Date: 2026-04-17
Owner: `$planner`
Status: `PASS`

## Purpose

This plan turns the admitted third-wave scenario set into real v2 bundle roots under
`Scenarios-v2/` without reopening the accepted redesign stack, the completed first-wave and
second-wave roots, the completed adapter pair, scoring rules, or provider execution policy.

The admitted set below is derived from the accepted redesign stack, the current status checkpoint,
`scenario-backlog-v1-2026-04-17.md`, and the accepted first-wave plus second-wave materialization
patterns.

The admitted wave stays balanced by design:

- create exactly one new real bundle from each remaining non-adapter pack `P01..P06`
- write only under new sibling roots in `Scenarios-v2/`
- treat the accepted first-wave and second-wave roots as reference-only, not mutable surfaces
- stop before provider reruns, scoring updates, result-table rewrites, or checkpoint changes

All paths below are relative to the benchmarks worktree root `D:/dev/Orchestrator/benchmarks/`.

## Admitted bundle set

| Pack | Scenario | Surface | Planned root | Reason for admission |
|---|---|---|---|---|
| `P01` | `S04` | `R04 $knowledge-archivist` | `Scenarios-v2/S04-knowledge-archivist-source-of-truth-update/` | fills the remaining hygiene surface and adds the still-unmaterialized archive or canonical-source modality |
| `P02` | `S09` | `R09 $planner` | `Scenarios-v2/S09-planner-phased-delivery-plan/` | fills the remaining planning surface and adds the still-unmaterialized phased-delivery modality |
| `P03` | `S11` | `R11 $computational-scientist` | `Scenarios-v2/S11-computational-scientist-model-validation-memo/` | broadens the scientist pack with the remaining numerical or physical reasoning modality instead of repeating the formal-proof or security-constraint shapes already present |
| `P04` | `S19` | `R19 $data-engineer` | `Scenarios-v2/S19-data-engineer-pipeline-patch/` | adds the first data-pipeline or SQL implementation bundle and keeps the general implementation pack broader than web plus toolchain only |
| `P05` | `S23` | `R23 $graphics-engineer` | `Scenarios-v2/S23-graphics-engineer-rendering-patch/` | adds the first rendering or graphics specialty bundle without reopening the already-complete Qt or geometry roots |
| `P06` | `S29` | `R29 $accessibility-reviewer` | `Scenarios-v2/S29-accessibility-review-findings/` | adds the first accessibility gate bundle and widens review coverage beyond the already-complete QA and architecture-review roots |

## Wave-wide rules

| Rule | Requirement |
|---|---|
| write boundary | this wave may add files only under the six planned third-wave roots in `Scenarios-v2/` |
| protected existing scenario roots | do not edit `Scenarios-v2/S02-lead-recovery-packet/`, `S03-consultant-tradeoff-memo/`, `S06-analyst-repository-fact-memo/`, `S07-architect-multi-seam-adr/`, `S10-algorithm-invariant-proof-memo/`, `S12-security-trust-boundary-package/`, `S16-frontend-web-ui-patch/`, `S17-qt-desktop-ui-patch/`, `S21-toolchain-ownership-patch/`, `S22-geometry-predicate-patch/`, `S25-qa-verification-verdict/`, `S26-architecture-review-findings/`, `S32-external-worker-transport-fidelity/`, or `S33-external-reviewer-transport-fidelity/` |
| protected planning surfaces | do not edit `Work/next-upgraded-pack/Planning/next-phase/*.md`, including the accepted redesign stack, the first-wave plan, and the second-wave plan |
| protected evidence surfaces | do not edit `Work/next-upgraded-pack/Checkpoints/**`, `Work/next-upgraded-pack/Evidence/**`, or `Work/next-upgraded-pack/Results-drafts/**` in this wave |
| protected legacy surfaces | do not edit `Work/next-upgraded-pack/Fixtures/**`, `Work/next-upgraded-pack/Tooling/**`, or `Archive/**`; legacy upgraded-pack assets remain reference-only |
| bundle contract | every admitted root must contain `scenario.yaml`, `README.md`, `inputs/`, `candidate/`, `oracle/`, and `verifiers/` |
| identity discipline | v2 bundle metadata must use `Snn`, `Rnn`, and `Pnn` only; old `Tnn`, `Lnn`, `Onn`, or adapter IDs may appear only as reference notes inside bundle-local materials |
| overlay discipline | all admitted third-wave roots must keep `overlay_flags: []`; this wave must not introduce new `browser-required` or `external-transport` roots |
| memo and review discipline | `S04`, `S09`, and `S11` stay packet or memo-only; `S29` stays findings-only review; none of those roots may embed implementation work as the editable candidate surface |
| implementation discipline | only `S19` and `S23` may contain code-bearing candidate trees; they must stay bundle-local and must not reopen shared tooling, runners, or existing scenario roots |
| adapter closure | `S32` and `S33` are already complete; no third-wave root may reuse adapter transport evidence as semantic role evidence or reopen the adapter lane |
| no reruns yet | no provider rerun, scoring update, ranking update, or publication-table rewrite is part of this wave |
| no task-memory expansion | do not create `work-items/` scaffolding or other repo task-memory additions as part of this plan |

## Phase order

`Phase 1` anchors the wave with the hygiene packet because it establishes the archive or
source-of-truth bundle pattern that is still missing from `Scenarios-v2/`.

After `Phase 1` passes:

- `Phases 2-3` are independent packet or memo additions and may run in parallel because their
  write surfaces do not overlap and their contracts are fixed by the accepted docs.
- `Phases 4-5` are independent implementation-root additions and may run in parallel after
  `Phases 2-3 PASS`, because the document-first conventions are then stable and the two candidate
  trees stay in separate general-vs-specialty implementation packs.
- `Phase 6` stays after the implementation roots so the accessibility-review bundle can inherit the
  now-live third-wave implementation conventions without becoming a patch root or reopening the
  existing QA or architecture-review bundles.
- integration starts only after all six admitted roots are present, followed by the mandatory
  `integration -> QA -> architecture-review` gate chain.

## Phase 1 - Materialize `P01 / S04`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S04-knowledge-archivist-source-of-truth-update/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | accepted third-wave planning inputs and the existing first-wave plus second-wave roots as reference only; no prior third-wave phase |
| allowed change surface | `Scenarios-v2/S04-knowledge-archivist-source-of-truth-update/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, especially the accepted `S02` and `S03` roots and the no-edit rule for all existing scenario roots |
| checks | confirm `scenario.yaml` matches `S04`, `R04`, `P01`, `hygiene`, `source-of-truth update packet`, `archive and source-of-truth hygiene`, the shared owner/advisory/factual/design/planning score profile, and `overlay_flags: []`; confirm the candidate surface is a source-of-truth packet only; confirm inputs, oracle, and verifiers require canonical-source reconciliation, archive hygiene, explicit update targets, and prohibition on silent policy invention |
| acceptance criteria | `S04` clearly benchmarks knowledge-archivist source-of-truth maintenance rather than lead orchestration, consultant advice, or implementation work; the bundle is self-contained and aligned with the accepted pack specs |
| rollback notes | delete only `Scenarios-v2/S04-knowledge-archivist-source-of-truth-update/` |

## Phase 2 - Materialize `P02 / S09`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S09-planner-phased-delivery-plan/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | `Phase 1 PASS` |
| allowed change surface | `Scenarios-v2/S09-planner-phased-delivery-plan/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted `S04` root |
| checks | confirm `scenario.yaml` matches `S09`, `R09`, `P02`, `planning`, `phase plan`, `phased delivery planning`, the shared owner/advisory/factual/design/planning score profile, and `overlay_flags: []`; confirm the candidate surface is one phased-delivery plan only; confirm inputs include accepted upstream brief or design artifacts rather than raw noisy discovery; confirm oracle and verifiers require ordered phases, explicit file scope, dependencies, tests, checks, and rollback notes without implementation code |
| acceptance criteria | `S09` clearly benchmarks planner-style execution planning rather than analyst fact gathering, architecture redesign, or code generation; the bundle preserves the plan-only artifact contract |
| rollback notes | delete only `Scenarios-v2/S09-planner-phased-delivery-plan/` |

## Phase 3 - Materialize `P03 / S11`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S11-computational-scientist-model-validation-memo/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$knowledge-archivist` |
| dependencies | `Phase 1 PASS` |
| allowed change surface | `Scenarios-v2/S11-computational-scientist-model-validation-memo/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted `S04` root |
| checks | confirm `scenario.yaml` matches `S11`, `R11`, `P03`, `scientist`, `model and validation memo`, `numerical or physical reasoning`, the `scientist, constraints` score profile, and `overlay_flags: []`; confirm the bundle remains non-web and memo-only; confirm inputs, oracle, and verifiers require governing equations or model assumptions, units or invariants, validation criteria, and explicit uncertainty or limitation handling; confirm the bundle does not drift into production code, generic architecture prose, or security or performance policy writing |
| acceptance criteria | `S11` clearly benchmarks computational-scientist reasoning rather than algorithm-proof framing, security constraint writing, or implementation repair; the bundle stays evidence-heavy and role-correct for `P03` |
| rollback notes | delete only `Scenarios-v2/S11-computational-scientist-model-validation-memo/` |

## Phase 4 - Materialize `P04 / S19`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S19-data-engineer-pipeline-patch/**` |
| file scope | one new sibling root with the required six top-level bundle entries and a bundle-local data workspace only |
| recommended materialization owner | `$data-engineer` |
| dependencies | `Phases 2-3 PASS` |
| allowed change surface | `Scenarios-v2/S19-data-engineer-pipeline-patch/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted third-wave memo roots |
| checks | confirm `scenario.yaml` matches `S19`, `R19`, `P04`, `implementation`, `code or query patch plus validation`, `SQL, ETL, or data pipeline`, the `implementation` score profile, and `overlay_flags: []`; confirm the candidate surface stays inside a bundle-local data pipeline or SQL workspace and its direct validation route only; confirm inputs, oracle, and verifiers encode owner-seam discipline, schema or contract expectations, and forbidden widening into shared runners, infra config, or results surfaces; confirm the root remains non-browser and non-adapter |
| acceptance criteria | `S19` adds a distinct data-engineering implementation bundle that is clearly separate from the already-complete web, toolchain, and geometry roots; it remains bounded, local, and role-correct for `P04` |
| rollback notes | delete only `Scenarios-v2/S19-data-engineer-pipeline-patch/` |

## Phase 5 - Materialize `P05 / S23`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S23-graphics-engineer-rendering-patch/**` |
| file scope | one new sibling root with the required six top-level bundle entries and a bundle-local rendering workspace only |
| recommended materialization owner | `$graphics-engineer` |
| dependencies | `Phases 2-3 PASS` |
| allowed change surface | `Scenarios-v2/S23-graphics-engineer-rendering-patch/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and the accepted third-wave memo roots |
| checks | confirm `scenario.yaml` matches `S23`, `R23`, `P05`, `implementation`, `code patch plus validation`, `rendering or graphics pipeline`, the `implementation` score profile, and `overlay_flags: []`; confirm the candidate surface stays inside a graphics-owned bundle-local root and its direct tests only; confirm inputs, oracle, and verifiers encode rendering intent, deterministic expected outputs or anchors, and forbidden widening into existing Qt, web UI, geometry, or visualization roots; confirm the root does not introduce screenshot-baseline maintenance outside the bundle |
| acceptance criteria | `S23` adds the first graphics-engineer specialty bundle, stays distinct from the already-complete Qt and geometry roots, and preserves the non-web specialty implementation boundary of `P05` |
| rollback notes | delete only `Scenarios-v2/S23-graphics-engineer-rendering-patch/` |

## Phase 6 - Materialize `P06 / S29`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S29-accessibility-review-findings/**` |
| file scope | one new sibling root with the required six top-level bundle entries only |
| recommended materialization owner | `$accessibility-reviewer` |
| dependencies | `Phases 4-5 PASS` |
| allowed change surface | `Scenarios-v2/S29-accessibility-review-findings/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, all accepted existing scenario roots, and all previously accepted third-wave roots |
| checks | confirm `scenario.yaml` matches `S29`, `R29`, `P06`, `review`, `review findings`, `accessibility gate`, the `review, QA` score profile, and `overlay_flags: []`; confirm the candidate surface is a findings-only accessibility report; confirm inputs, oracle, and verifiers encode keyboard access, semantic labeling, focus order, contrast or AT exposure expectations, and false-positive traps; confirm the bundle does not embed code patching, semantic QA verdict substitution, or browser-only overlays as the editable surface |
| acceptance criteria | `S29` clearly benchmarks accessibility-review findings and stays distinct from the already-complete QA-verdict and architecture-review roots; review-only separation remains intact |
| rollback notes | delete only `Scenarios-v2/S29-accessibility-review-findings/` |

## Integration owner and wave gate

| Item | Requirement |
|---|---|
| integration owner | `$knowledge-archivist` |
| integration responsibilities | assemble the six admitted third-wave roots into the existing `Scenarios-v2/` tree; confirm the exact admitted set added by this wave is `S04`, `S09`, `S11`, `S19`, `S23`, and `S29`; confirm all fourteen existing roots remain unchanged; confirm every new metadata row still matches `scenario-backlog-v1`, `pack-specs-v1`, and `scoring-and-results-model`; confirm all six new roots keep `overlay_flags: []`; confirm no protected surfaces changed |
| mandatory integration gate | integration must finish before QA starts; the integration memo must treat the first-wave and second-wave roots as protected reference-only surfaces and must confirm the completed adapter pair remains untouched |
| mandatory QA gate | `$qa-engineer` must verify required bundle structure, metadata alignment, local verifier presence or execution, diff isolation, and the packet-vs-implementation-vs-review separation before any third-wave root is treated as v2-ready |
| mandatory review gate | `$architecture-reviewer` must verify pack cohesion, hygiene-planning-scientist-implementation-review separation, data-vs-graphics boundary integrity, protected-root isolation, and absence of taxonomy or scoring drift before any third-wave root is treated as v2 evidence |
| non-mandatory conditional gate | add `$ui-test-engineer` only if `S23` or `S29` widens into screenshot baselines, image-diff harnesses, or visual-fixture maintenance beyond bundle-local verifiers |
| whole-wave rollback | because the wave is additive-only, rollback is bundle-by-bundle deletion of the six third-wave roots under `Scenarios-v2/`; do not compensate by editing existing scenario roots, accepted planning docs, evidence docs, checkpoints, results drafts, or legacy fixture or archive surfaces |

## Recommended next role sequence

1. `$lead` accepts this plan and routes `Phase 1`.
2. `$knowledge-archivist` materializes `Phase 1` and remains the integration owner throughout the wave.
3. `$knowledge-archivist` materializes `Phases 2-3`.
4. `$data-engineer` materializes `Phase 4`.
5. `$graphics-engineer` materializes `Phase 5`.
6. `$accessibility-reviewer` materializes `Phase 6`.
7. `$knowledge-archivist` performs the mandatory integration pass and hands the expanded `Scenarios-v2/` tree to verification.
8. `$qa-engineer` performs the mandatory wave gate.
9. `$architecture-reviewer` performs the mandatory pre-evidence review.
10. `$ui-test-engineer` runs only if the conditional visual-fixture gate is triggered by the materialized bundle contents.

## Gate decision

`PASS` - the lead can accept the third-wave materialization plan and route the first third-wave
implementation phase without reopening the completed adapter lane, prior-wave roots, or any
accepted redesign or results surfaces.

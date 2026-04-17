Date: 2026-04-17
Owner: `$planner`
Status: `PASS`

## Purpose

This plan turns the accepted v1 redesign stack into the first implementation wave for real v2
bundle roots.

The admitted wave is narrow by design:

- create exactly one real scenario bundle from each of `P01..P07`
- write only under the new `Scenarios-v2/` root
- stop before provider reruns, result ranking updates, or taxonomy changes

All paths below are relative to the benchmarks worktree root `D:/dev/Orchestrator/benchmarks/`.

## Admitted bundle set

| Pack | Scenario | Surface | Planned root | Reason for admission |
|---|---|---|---|---|
| `P01` | `S02` | `R02 $lead` | `Scenarios-v2/S02-lead-recovery-packet/` | worked example for owner-orchestration packet bundles |
| `P02` | `S07` | `R07 $architect` | `Scenarios-v2/S07-architect-multi-seam-adr/` | worked example for design-packet bundles |
| `P03` | `S12` | `R12 $security-engineer` | `Scenarios-v2/S12-security-trust-boundary-package/` | worked example for evidence-heavy constraint bundles |
| `P04` | `S21` | `R21 $toolchain-engineer` | `Scenarios-v2/S21-toolchain-ownership-patch/` | worked example for bounded implementation bundles |
| `P05` | `S22` | `R22 $geometry-engineer` | `Scenarios-v2/S22-geometry-predicate-patch/` | worked example for non-web specialty implementation bundles |
| `P06` | `S26` | `R26 $architecture-reviewer` | `Scenarios-v2/S26-architecture-review-findings/` | worked example for findings-only review bundles |
| `P07` | `S32` | `A01 $external-worker` | `Scenarios-v2/S32-external-worker-transport-fidelity/` | worked example for adapter-only transport bundles |

## Wave-wide rules

| Rule | Requirement |
|---|---|
| write boundary | the whole wave may add files only under `Scenarios-v2/` |
| protected planning surfaces | do not edit `Work/next-upgraded-pack/Planning/next-phase/*.md`, including the accepted redesign stack |
| protected evidence surfaces | do not edit `Work/next-upgraded-pack/Checkpoints/**`, `Work/next-upgraded-pack/Evidence/**`, or `Work/next-upgraded-pack/Results-drafts/**` in this wave |
| protected legacy surfaces | do not edit `Work/next-upgraded-pack/Fixtures/**`, `Work/next-upgraded-pack/Tooling/**`, or `Archive/**`; legacy `T/L/O` assets are reference only |
| bundle contract | every admitted root must contain `scenario.yaml`, `README.md`, `inputs/`, `candidate/`, `oracle/`, and `verifiers/` |
| identity discipline | v2 bundle metadata must use `Snn`, `Rnn`, `Ann`, and `Pnn` only; old `Tnn` or line-family names may appear only as reference notes inside inputs or oracle material |
| adapter separation | `P07` stays adapter-only; no adapter artifact may be used as semantic role evidence |
| no reruns yet | no provider rerun, scoring update, ranking update, or publication-table rewrite is part of this wave |
| no task-memory expansion | do not create `work-items/` stubs or other task-memory scaffolding for this plan |

## Phase order

`Phase 1` is the convention-setting bootstrap because `Scenarios-v2/` does not exist yet.

After `Phase 1` passes, `Phases 2..7` are independent sibling-root additions. They may run
sequentially or in parallel because their write surfaces do not overlap, but QA and review start
only after the integration owner confirms all admitted roots are present.

## Phase 1 - Bootstrap `Scenarios-v2` with `P01 / S02`

| Item | Plan |
|---|---|
| scope | create the new root directory and materialize `Scenarios-v2/S02-lead-recovery-packet/**` |
| recommended implementation owner | `$knowledge-archivist` |
| dependencies | accepted redesign docs; no prior implementation phase |
| allowed change surface | `Scenarios-v2/` and `Scenarios-v2/S02-lead-recovery-packet/**` only |
| must-not-break surfaces | all wave-wide protected surfaces; no sibling `Snn` roots yet |
| checks | confirm `scenario.yaml` fields match `S02`, `R02`, `P01`, `owner`, and the planning-profile score family; confirm the required six bundle entries exist; confirm README, inputs, oracle, and verifiers all describe orchestration-recovery behavior rather than generic planning; confirm the diff is isolated to the `S02` root |
| acceptance criteria | `S02` is a real bundle, not a placeholder shell; it can stand as the canonical first example for packet-style v2 bundles; it does not reuse old `T/L/O` naming as the primary identity |
| rollback notes | delete only `Scenarios-v2/S02-lead-recovery-packet/`; if `Scenarios-v2/` is otherwise empty, delete the empty root too |

## Phase 2 - Materialize `P02 / S07`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S07-architect-multi-seam-adr/**` |
| recommended implementation owner | `$knowledge-archivist` |
| dependencies | `Phase 1 PASS` |
| allowed change surface | `Scenarios-v2/S07-architect-multi-seam-adr/**` only |
| must-not-break surfaces | all wave-wide protected surfaces and the accepted `S02` root |
| checks | confirm `scenario.yaml` matches `S07`, `R07`, `P02`, `design`, and the planning-profile score family; confirm inputs capture a multi-seam architecture choice; confirm candidate scope is ADR or design packet only; confirm oracle and verifiers anchor seam choice, tradeoff coverage, and dependency-direction claims; confirm no implementation files or planning docs are changed outside the bundle |
| acceptance criteria | `S07` clearly benchmarks architecture decision quality rather than analyst fact gathering or planner sequencing; the bundle stays self-contained and aligned with the accepted pack specs |
| rollback notes | delete only `Scenarios-v2/S07-architect-multi-seam-adr/` |

## Phase 3 - Materialize `P03 / S12`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S12-security-trust-boundary-package/**` |
| recommended implementation owner | `$knowledge-archivist` |
| dependencies | `Phase 1 PASS` |
| allowed change surface | `Scenarios-v2/S12-security-trust-boundary-package/**` only |
| must-not-break surfaces | all wave-wide protected surfaces and the accepted `S02` root |
| checks | confirm `scenario.yaml` matches `S12`, `R12`, `P03`, `constraint`, and the scientist-constraints score family; confirm the bundle remains non-web and evidence-heavy; confirm inputs/oracle/verifiers capture trust boundaries, threat classes, and required controls; confirm no real secrets, live credentials, or provider-specific runtime material are introduced |
| acceptance criteria | `S12` is a real security-constraint bundle with explicit evidence anchors and no sensitive-data leakage; it does not drift into implementation or review-only semantics |
| rollback notes | delete only `Scenarios-v2/S12-security-trust-boundary-package/` |

## Phase 4 - Materialize `P04 / S21`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S21-toolchain-ownership-patch/**` |
| recommended implementation owner | `$toolchain-engineer` |
| dependencies | `Phase 1 PASS`; prefer `Phases 2-3 PASS` first so packet-style conventions are already stable |
| allowed change surface | `Scenarios-v2/S21-toolchain-ownership-patch/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, plus no edits to `Work/next-upgraded-pack/Tooling/run-active-cohort-batch.ps1` or legacy `Work/next-upgraded-pack/Fixtures/T29-*` roots |
| checks | confirm `scenario.yaml` matches `S21`, `R21`, `P04`, `implementation`, and the implementation score family; confirm candidate scope is limited to toolchain-owned files inside the bundle; confirm oracle and verifiers encode the owner seam, passing command or validation route, and forbidden widening paths; confirm `overlay_flags` stays `[]`; confirm any legacy `T29` inspiration is translated into v2 structure instead of copied as canonical `broken/control-pass` semantics |
| acceptance criteria | `S21` is a bounded implementation bundle that expresses owner-seam discipline without changing the current legacy runner or fixture registry; it remains non-web and role-correct for `P04` |
| rollback notes | delete only `Scenarios-v2/S21-toolchain-ownership-patch/` |

## Phase 5 - Materialize `P05 / S22`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S22-geometry-predicate-patch/**` |
| recommended implementation owner | `$geometry-engineer` |
| dependencies | `Phase 1 PASS`; prefer `Phase 4 PASS` first so the first code-bearing bundle is already established |
| allowed change surface | `Scenarios-v2/S22-geometry-predicate-patch/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, plus no edits to legacy geometry, graphics, or visualization fixtures |
| checks | confirm `scenario.yaml` matches `S22`, `R22`, `P05`, `implementation`, and the implementation score family; confirm inputs and oracle describe deterministic geometry cases, tolerances, and edge conditions; confirm candidate scope stays inside a geometry-owned root and direct tests only; confirm the bundle stays non-web and does not spill into renderer or UI semantics |
| acceptance criteria | `S22` is a real specialty implementation bundle with explicit geometry truth anchors and local validation expectations; it preserves the non-web specialty identity of `P05` |
| rollback notes | delete only `Scenarios-v2/S22-geometry-predicate-patch/` |

## Phase 6 - Materialize `P06 / S26`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S26-architecture-review-findings/**` |
| recommended implementation owner | `$knowledge-archivist` |
| dependencies | `Phase 1 PASS` |
| allowed change surface | `Scenarios-v2/S26-architecture-review-findings/**` only |
| must-not-break surfaces | all wave-wide protected surfaces and all accepted bundle roots from earlier phases |
| checks | confirm `scenario.yaml` matches `S26`, `R26`, `P06`, `review`, and the review-QA score family; confirm README and candidate instructions stay findings-only; confirm inputs, oracle, and verifiers encode severity anchors, supporting references, and false-positive traps; confirm no code patching path is embedded in the review bundle |
| acceptance criteria | `S26` cleanly benchmarks architecture review behavior and cannot be mistaken for an implementation or design bundle; review-only separation remains intact |
| rollback notes | delete only `Scenarios-v2/S26-architecture-review-findings/` |

## Phase 7 - Materialize `P07 / S32`

| Item | Plan |
|---|---|
| scope | add `Scenarios-v2/S32-external-worker-transport-fidelity/**` |
| recommended implementation owner | `$platform-engineer` |
| dependencies | `Phase 1 PASS`; prefer `Phase 6 PASS` first so the review-style reporting contract is already visible |
| allowed change surface | `Scenarios-v2/S32-external-worker-transport-fidelity/**` only |
| must-not-break surfaces | all wave-wide protected surfaces, plus no edits to provider wrappers, runtime credential surfaces, or semantic result tables |
| checks | confirm `scenario.yaml` matches `S32`, `A01`, `P07`, `adapter`, the adapters score family, and `overlay_flags: [external-transport]`; confirm inputs/oracle/verifiers are transport-only and require provenance fields; confirm candidate scope is adapter report only; confirm no semantic role scorecard logic, provider ranking content, or hidden fallback behavior is embedded in the bundle |
| acceptance criteria | `S32` stays adapter-only, transport-only, and clearly separate from semantic role evidence; the bundle does not force any runtime-wrapper change as part of this admitted wave |
| rollback notes | delete only `Scenarios-v2/S32-external-worker-transport-fidelity/` |

## Integration owner and wave gate

| Item | Requirement |
|---|---|
| integration owner | `$knowledge-archivist` |
| integration responsibilities | assemble the seven admitted roots into one coherent `Scenarios-v2/` tree; confirm the exact admitted set is `S02`, `S07`, `S12`, `S21`, `S22`, `S26`, and `S32`; confirm every bundle metadata row still matches `scenario-backlog-v1`, `pack-specs-v1`, and `scoring-and-results-model`; confirm no protected surfaces changed |
| mandatory QA gate | `$qa-engineer` must verify required bundle structure, metadata alignment, verifier presence, and diff isolation before any bundle is treated as v2-ready |
| mandatory review gate | `$architecture-reviewer` must verify contract cohesion, pack separation, adapter isolation, and absence of taxonomy or scoring drift before any bundle is treated as v2 evidence |
| non-mandatory conditional gate | add `$security-reviewer` only if implementation widens into provider credentials, runtime wrappers, or network-executing tooling outside bundle-local materials |
| whole-wave rollback | because the wave is additive-only, rollback is bundle-by-bundle deletion under `Scenarios-v2/`; do not compensate by editing accepted planning, evidence, or legacy fixture surfaces |

## Recommended next role sequence

1. `$lead` accepts this plan and routes `Phase 1`.
2. `$knowledge-archivist` materializes `Phases 1`, `2`, `3`, and `6`, and remains the integration owner throughout the wave.
3. `$toolchain-engineer` materializes `Phase 4`.
4. `$geometry-engineer` materializes `Phase 5`.
5. `$platform-engineer` materializes `Phase 7`.
6. `$knowledge-archivist` performs the integration pass and hands the complete `Scenarios-v2/` tree to verification.
7. `$qa-engineer` performs the mandatory wave gate.
8. `$architecture-reviewer` performs the mandatory pre-evidence review.

## Gate decision

`PASS` - the lead can route the first implementation phase without reopening taxonomy, scoring, or
pack membership.

Date: 2026-04-17
Owner: `$qa-engineer`
Status: `PASS`

# Second-Wave Scenario Materialization QA Report

## Purpose

Verify the mandatory QA gate for the admitted second-wave `Scenarios-v2` materialization. Scope was
limited to required bundle structure, metadata alignment with the accepted planning stack, local
verifier presence and execution, diff-isolation smoke checks, and the browser-vs-Qt modality split
for:

- `S03-consultant-tradeoff-memo`
- `S06-analyst-repository-fact-memo`
- `S10-algorithm-invariant-proof-memo`
- `S16-frontend-web-ui-patch`
- `S17-qt-desktop-ui-patch`
- `S25-qa-verification-verdict`
- `S33-external-reviewer-transport-fidelity`

## Approved inputs checked

- `Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md`
- `Work/next-upgraded-pack/Planning/next-phase/scenario-backlog-v1-2026-04-17.md`
- `Work/next-upgraded-pack/Planning/next-phase/pack-specs-v1-2026-04-17.md`
- `Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-integration-2026-04-17.md`
- `Scenarios-v2/S03-consultant-tradeoff-memo/`
- `Scenarios-v2/S06-analyst-repository-fact-memo/`
- `Scenarios-v2/S10-algorithm-invariant-proof-memo/`
- `Scenarios-v2/S16-frontend-web-ui-patch/`
- `Scenarios-v2/S17-qt-desktop-ui-patch/`
- `Scenarios-v2/S25-qa-verification-verdict/`
- `Scenarios-v2/S33-external-reviewer-transport-fidelity/`

## Executed checks

### Root inventory and required structure

- Confirmed the exact admitted second-wave set only: `S03`, `S06`, `S10`, `S16`, `S17`, `S25`,
  `S33`.
- Listed the top-level contents of each admitted root and confirmed the required six entries are
  present in all seven bundles: `scenario.yaml`, `README.md`, `inputs/`, `candidate/`, `oracle/`,
  `verifiers/`.
- Confirmed the seeded directories are non-empty rather than placeholder shells:

| Bundle | `inputs/` files | `candidate/` files | `oracle/` files | `verifiers/` files |
|---|---:|---:|---:|---:|
| `S03` | 6 | 2 | 5 | 2 |
| `S06` | 4 | 18 | 5 | 2 |
| `S10` | 7 | 2 | 7 | 2 |
| `S16` | 6 | 11 | 5 | 2 |
| `S17` | 5 | 9 | 5 | 3 |
| `S25` | 8 | 2 | 7 | 2 |
| `S33` | 6 | 2 | 5 | 2 |

### Metadata alignment

I cross-checked each observed `scenario.yaml` against the admitted rows in the accepted wave-2
plan, the backlog, and the pack spec:

| Scenario | Observed metadata | Alignment result |
|---|---|---|
| `S03` | `R03`, `P01`, `advisory`, `advisory memo`, `tradeoff memo`, `owner, advisory, factual, design, planning`, `[]` | matches |
| `S06` | `R06`, `P02`, `factual`, `factual research memo`, `repository investigation`, `owner, advisory, factual, design, planning`, `[]` | matches |
| `S10` | `R10`, `P03`, `scientist`, `invariant and proof memo`, `formal reasoning`, `scientist, constraints`, `[]` | matches |
| `S16` | `R16`, `P04`, `implementation`, `code patch plus local verification`, `web UI`, `implementation`, `[browser-required]` | matches |
| `S17` | `R17`, `P05`, `implementation`, `code patch plus local verification`, `Qt desktop UI`, `implementation`, `[]` | matches |
| `S25` | `R25`, `P06`, `review`, `QA report and test verdict`, `verification and test design`, `review, QA`, `[]` | matches |
| `S33` | `A02`, `P07`, `adapter`, `transport execution report`, `transport fidelity`, `adapters`, `[external-transport]` | matches |

No second-wave bundle used legacy `Tnn`, `Lnn`, or `Onn` identifiers as primary identity
metadata.

### Local verifier execution

I ran the bundle-local author or template validation commands from
`D:\dev\Orchestrator\benchmarks`:

| Bundle | Command | Result |
|---|---|---|
| `S03` | `python Scenarios-v2/S03-consultant-tradeoff-memo/verifiers/check_consultant_memo.py --bundle-shape-only` | PASS |
| `S06` | `python Scenarios-v2/S06-analyst-repository-fact-memo/verifiers/check_factual_memo.py --bundle-shape-only` | PASS |
| `S10` | `python Scenarios-v2/S10-algorithm-invariant-proof-memo/verifiers/check_algorithm_invariant_proof_memo.py --bundle-shape-only` | PASS |
| `S16` | `python Scenarios-v2/S16-frontend-web-ui-patch/verifiers/check_s16_frontend_bundle.py --bundle-shape-only` | PASS |
| `S17` | `python Scenarios-v2/S17-qt-desktop-ui-patch/verifiers/run_qt_ui_checks.py --bundle-shape-only` | PASS |
| `S17` | `python Scenarios-v2/S17-qt-desktop-ui-patch/verifiers/run_qt_ui_checks.py --expect-start-state` | PASS |
| `S17` | `python Scenarios-v2/S17-qt-desktop-ui-patch/verifiers/check_scope.py` | PASS |
| `S25` | `python Scenarios-v2/S25-qa-verification-verdict/verifiers/check_qa_verdict.py --bundle-shape-only` | PASS |
| `S33` | `python Scenarios-v2/S33-external-reviewer-transport-fidelity/verifiers/check_transport_report.py --mode template` | PASS |

The implementation-bundle extras required by the admitted scope also behaved correctly:

- `S16`: `node scripts/verify-ui-contract.mjs` from
  `Scenarios-v2/S16-frontend-web-ui-patch/candidate/workspace/` exited with the expected failing
  baseline evidence. The output reported missing loading-state `role=status` and `aria-live`,
  missing semantic pressed-state filter buttons, missing result-summary and reset-action contract,
  missing error-state `role=alert` and retry copy, and missing focus-visible CSS selectors. This is
  the intended pre-fix browser baseline for the seeded implementation bundle rather than a
  materialization defect.
- `S16`: `python Scenarios-v2/S16-frontend-web-ui-patch/verifiers/check_s16_frontend_bundle.py`
  also failed in completed-run mode for the same reason, which is consistent with an intentionally
  unpatched seeded candidate.
- `S17`: `--expect-start-state` confirmed the seeded Qt candidate still exhibits the intended
  desktop-specific failures and no unexpected extras.
- `S17`: `check_scope.py` confirmed the declared editable surface stays inside the Qt dialog module
  and its direct test file only.

I did not run completed-run verifiers for `S03`, `S06`, `S10`, `S25`, or `S33` because this gate
is for author-side bundle materialization, and those modes require filled candidate artifacts rather
than seeded templates.

### Browser-vs-Qt modality split

The integrated second-wave set preserves the required browser-vs-Qt boundary:

- `S16` is the only admitted second-wave root with `overlay_flags: [browser-required]`.
- `S16` declares `modality_family: web UI`, its README requires the browser-local validation route
  `node scripts/verify-ui-contract.mjs`, and its candidate surface is a browser workspace under
  `candidate/workspace/`.
- `S17` declares `modality_family: Qt desktop UI` with `overlay_flags: []`.
- `S17` README and inputs explicitly enforce the non-browser boundary, and the scope verifier keeps
  the editable surface inside `candidate/qt-settings-dialog/...` only.
- The remaining second-wave roots stay non-browser semantic memo, review, or adapter bundles.

### Diff isolation and must-not-break smoke checks

- `git rev-parse --show-toplevel` confirmed `D:/dev/Orchestrator/benchmarks` is the active Git
  worktree root.
- `git status --short --untracked-files=all -- Scenarios-v2/S03-consultant-tradeoff-memo Scenarios-v2/S06-analyst-repository-fact-memo Scenarios-v2/S10-algorithm-invariant-proof-memo Scenarios-v2/S16-frontend-web-ui-patch Scenarios-v2/S17-qt-desktop-ui-patch Scenarios-v2/S25-qa-verification-verdict Scenarios-v2/S33-external-reviewer-transport-fidelity`
  showed additive untracked files only under the seven admitted second-wave roots.
- `git status --short -- Scenarios-v2/S02-lead-recovery-packet Scenarios-v2/S07-architect-multi-seam-adr Scenarios-v2/S12-security-trust-boundary-package Scenarios-v2/S21-toolchain-ownership-patch Scenarios-v2/S22-geometry-predicate-patch Scenarios-v2/S26-architecture-review-findings Scenarios-v2/S32-external-worker-transport-fidelity Work/next-upgraded-pack/Checkpoints Work/next-upgraded-pack/Results-drafts PLAN.md Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-integration-2026-04-17.md`
  showed only:
  - `?? PLAN.md`
  - `?? Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-integration-2026-04-17.md`
  - `?? Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md`

Per admitted scope and the integration memo:

- `Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md`
  was treated as accepted upstream planning context, not as a second-wave spill.
- `PLAN.md` was treated as unrelated pre-existing untracked context, consistent with the accepted
  integration memo treatment.
- `Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-integration-2026-04-17.md`
  was treated as the expected integration-owner evidence write for this wave.

No checkpoint, results-draft, or first-wave-root status entries were reported by the targeted smoke
check.

## Acceptance-criteria mapping

| Acceptance criterion | Evidence | Result |
|---|---|---|
| Required structure is present for the admitted second-wave set | top-level inventory checks across all seven roots; all required six-entry bundle contracts observed; `inputs/`, `candidate/`, `oracle/`, and `verifiers/` are populated | PASS |
| Metadata aligns with the accepted planning stack | `scenario.yaml` values for `id`, `surface_id`, `pack_id`, `role_class`, `artifact_type`, `modality_family`, `score_profile`, and `overlay_flags` matched the admitted plan, backlog, and pack-spec rows | PASS |
| Local verifier presence and execution are real, not placeholder-only | every bundle contains a local verifier under `verifiers/`; all author or template verifier runs passed; the admitted extra checks for `S16` and `S17` executed with the expected results | PASS |
| Browser-vs-Qt modality split stays intact | `S16` is the only second-wave browser-required root; `S17` remains explicit Qt desktop UI with non-browser scope; memo, review, and adapter bundles remain non-browser | PASS |
| Diff isolation and must-not-break surfaces are smoke-checked | Git-backed status reads showed additive second-wave roots only; first-wave roots, checkpoints, and results-drafts stayed clean; accepted upstream plan, integration memo, and unrelated `PLAN.md` were treated per the admitted scope | PASS |

## Findings and residual risk

### Advisory: `S17` start-state verifier emits transient Python bytecode

Running `python Scenarios-v2/S17-qt-desktop-ui-patch/verifiers/run_qt_ui_checks.py --expect-start-state`
emitted `__pycache__` files inside
`candidate/qt-settings-dialog/src/qt_settings_dialog/` while importing the bundle-local module. I
removed the transient cache immediately, and the final Git-backed isolation read no longer showed
those files.

This does not block the wave because the materialized bundle content, metadata, modality split, and
allowed verifier checks all passed, but it is a verifier-hygiene edge case worth tracking if later
automation requires strictly side-effect-free verification.

## QA gate decision

The admitted second-wave `Scenarios-v2` materialization satisfies the scoped QA gate for structure,
metadata alignment, local verifier execution, diff isolation, and the browser-vs-Qt modality split.

The integrated wave is ready to hand to `$architecture-reviewer`.

`PASS`

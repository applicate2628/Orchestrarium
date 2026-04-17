Date: 2026-04-17
Owner: `$architecture-reviewer`
Status: `PASS`

# Second-Wave Scenario Materialization Architecture Review

## Scope

Read-only architecture and cohesion gate for the admitted second-wave scenario materialization.
Approved inputs used for this review were:

- `Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md`
- `Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-integration-2026-04-17.md`
- `Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-qa-2026-04-17.md`
- `Scenarios-v2/S03-consultant-tradeoff-memo/`
- `Scenarios-v2/S06-analyst-repository-fact-memo/`
- `Scenarios-v2/S10-algorithm-invariant-proof-memo/`
- `Scenarios-v2/S16-frontend-web-ui-patch/`
- `Scenarios-v2/S17-qt-desktop-ui-patch/`
- `Scenarios-v2/S25-qa-verification-verdict/`
- `Scenarios-v2/S33-external-reviewer-transport-fidelity/`

Per admitted scope, I treated the wave-2 planning memo as accepted upstream context and `PLAN.md`
as unrelated pre-existing untracked context, consistent with the accepted integration and QA memos.

## Gate summary

No blocking architectural drift was found. The second-wave addition remains cohesive as an
additive sibling-root expansion under `Scenarios-v2/`, with preserved role separation, preserved
browser-vs-Qt boundaries, preserved QA-vs-adapter evidence separation, and no supported sign of
taxonomy or score-profile drift into protected surfaces.

## Claim verification

### 1. Exact admitted roots only

The accepted plan fixes the admitted wave-2 set to `S03`, `S06`, `S10`, `S16`, `S17`, `S25`, and
`S33` and assigns this review gate to confirm that exact set without widening
(`Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md:20`,
`:169`, `:171`).

That exact set is what the accepted integration memo records as present and nothing else
(`Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-integration-2026-04-17.md:35-63`),
and the accepted QA memo repeats the same bounded inventory
(`Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-qa-2026-04-17.md:38-41`).

Direct root inspection in this review matched that admitted set. I did not find any second-wave
bundle outside those seven roots.

### 2. Six-entry bundle contract and v2 identity are preserved

The plan requires every admitted root to contain exactly the six-entry v2 bundle contract and to
use `Snn`, `Rnn`, `Ann`, and `Pnn` identity rather than reopening legacy primary naming
(`Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md:41-42`).

The accepted integration memo records the required six-entry top-level shape for all seven roots
(`Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-integration-2026-04-17.md:65-78`),
and the accepted QA memo independently confirms the same bundle contract plus populated
subdirectories
(`Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-qa-2026-04-17.md:38-55`,
`:154-156`).

Direct root inspection in this review matched that evidence:

- each admitted root exposes only `scenario.yaml`, `README.md`, `inputs/`, `candidate/`,
  `oracle/`, and `verifiers/` at top level
- each `scenario.yaml` carries v2 identity fields and admitted pack/role metadata:
  - `S03`: `id: S03`, `surface_id: R03`, `pack_id: P01`, `role_class: advisory`
    (`Scenarios-v2/S03-consultant-tradeoff-memo/scenario.yaml:1-4`)
  - `S06`: `id: S06`, `surface_id: R06`, `pack_id: P02`, `role_class: factual`
    (`Scenarios-v2/S06-analyst-repository-fact-memo/scenario.yaml:1-4`)
  - `S10`: `id: S10`, `surface_id: R10`, `pack_id: P03`, `role_class: scientist`
    (`Scenarios-v2/S10-algorithm-invariant-proof-memo/scenario.yaml:1-4`)
  - `S16`: `id: S16`, `surface_id: R16`, `pack_id: P04`, `role_class: implementation`
    (`Scenarios-v2/S16-frontend-web-ui-patch/scenario.yaml:1-4`)
  - `S17`: `id: S17`, `surface_id: R17`, `pack_id: P05`, `role_class: implementation`
    (`Scenarios-v2/S17-qt-desktop-ui-patch/scenario.yaml:1-4`)
  - `S25`: `id: S25`, `surface_id: R25`, `pack_id: P06`, `role_class: review`
    (`Scenarios-v2/S25-qa-verification-verdict/scenario.yaml:1-4`)
  - `S33`: `id: S33`, `surface_id: A02`, `pack_id: P07`, `role_class: adapter`
    (`Scenarios-v2/S33-external-reviewer-transport-fidelity/scenario.yaml:1-4`)

I found no root whose primary identity drifted back to `Tnn`, `Lnn`, or `Onn`.

### 3. Advisory, factual, scientist, implementation, review, and adapter separation remains coherent

The accepted plan requires memo/review/adapter separation to stay explicit
(`Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md:44-45`,
`:171`).

Direct bundle review supports that separation:

- `S03` stays advisory-only. Its README says the candidate is not asked to route work, approve a
  phase, or turn the task into implementation or planning output
  (`Scenarios-v2/S03-consultant-tradeoff-memo/README.md:5`, `:23`), and the candidate contract
  keeps only `advisory-memo.md` editable while forbidding lead, planner, implementation, and
  adapter drift (`Scenarios-v2/S03-consultant-tradeoff-memo/candidate/README.md:7`, `:11-16`).
- `S06` stays factual-only. Its README forbids recommendations, architecture choice, and delivery
  planning (`Scenarios-v2/S06-analyst-repository-fact-memo/README.md:4-5`, `:19`, `:38`), and the
  candidate contract keeps only `repository-fact-memo.md` editable while treating the repo
  snapshot as read-only evidence
  (`Scenarios-v2/S06-analyst-repository-fact-memo/candidate/README.md:7`, `:12-16`). The noisiest
  material in the bundle, `candidate/repo-snapshot/**`, is explicitly immutable in `scenario.yaml`
  (`Scenarios-v2/S06-analyst-repository-fact-memo/scenario.yaml:13-14`), which keeps the decoy
  control-plane slice from becoming live coupling.
- `S10` stays scientist-only. Its README says the scored output is an algorithm note, not a code
  patch or generic architecture prose (`Scenarios-v2/S10-algorithm-invariant-proof-memo/README.md:21`,
  `:27`), and the candidate contract keeps only the proof memo editable and explicitly forbids
  widening into implementation or policy packages
  (`Scenarios-v2/S10-algorithm-invariant-proof-memo/candidate/README.md:5`, `:18`).
- `S16` and `S17` stay implementation-only, but on different platform seams. `S16` limits changes
  to three web UI files inside a bundle-local browser workspace
  (`Scenarios-v2/S16-frontend-web-ui-patch/scenario.yaml:8-10`) and frames the task as a bounded
  browser UI repair (`Scenarios-v2/S16-frontend-web-ui-patch/README.md:9`, `:16`). `S17` limits
  changes to the Qt dialog module and its direct test
  (`Scenarios-v2/S17-qt-desktop-ui-patch/scenario.yaml:8-9`) and frames the task as a bounded Qt
  Widgets repair (`Scenarios-v2/S17-qt-desktop-ui-patch/README.md:3`, `:22`, `:39`).
- `S25` stays review-only and QA-specific. Its `scenario.yaml` allows only `candidate/qa-verdict.md`
  (`Scenarios-v2/S25-qa-verification-verdict/scenario.yaml:8`), its README says the candidate does
  not patch code or review architecture
  (`Scenarios-v2/S25-qa-verification-verdict/README.md:4-5`, `:16`), and its candidate contract
  reinforces that this is a QA-only gate with no code patching or architecture redesign path
  (`Scenarios-v2/S25-qa-verification-verdict/candidate/README.md:5`, `:22-23`).
- `S33` stays adapter-only and transport-only. Its metadata is `A02 / adapter / transport
  execution report` (`Scenarios-v2/S33-external-reviewer-transport-fidelity/scenario.yaml:1-6`,
  `:14-16`), its README says no semantic reviewer findings or QA verdicts are scored here
  (`Scenarios-v2/S33-external-reviewer-transport-fidelity/README.md:3-6`, `:21`, `:33`, `:42`),
  and its candidate contract says only `transport-execution-report.md` is mutable and semantic
  review artifacts must not be added
  (`Scenarios-v2/S33-external-reviewer-transport-fidelity/candidate/README.md:3`, `:5`).

That role partitioning is coherent. Each bundle is understandable in isolation, and no bundle
quietly collapses into another role lane.

### 4. Browser-vs-Qt boundary remains coherent

The plan says only `S16` may carry `overlay_flags: [browser-required]`, and no other second-wave
root may require browser execution
(`Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md:43`).

Direct bundle review supports that boundary:

- `S16` is the only second-wave root declaring the browser overlay
  (`Scenarios-v2/S16-frontend-web-ui-patch/scenario.yaml:23-24`) and its README frames the
  mutable surface as a browser-capable release board with browser-local verification
  (`Scenarios-v2/S16-frontend-web-ui-patch/README.md:9`, `:24`).
- `S17` declares `overlay_flags: []`
  (`Scenarios-v2/S17-qt-desktop-ui-patch/scenario.yaml:19`) and its README plus explicit boundary
  note keep it in Qt-only territory (`Scenarios-v2/S17-qt-desktop-ui-patch/README.md:28`, `:44`;
  `Scenarios-v2/S17-qt-desktop-ui-patch/inputs/non-browser-boundary.md:11-14`).

This matches the accepted QA memo, which already verified `S16` as the only browser-required root
and `S17` as explicit non-browser Qt scope
(`Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-qa-2026-04-17.md:113-122`,
`:157`).

### 5. `S25` remains semantic QA evidence while `S33` remains adapter-only transport evidence

The plan requires this distinction explicitly
(`Work/next-upgraded-pack/Planning/next-phase/scenario-materialization-plan-wave-2-2026-04-17.md:44-45`,
`:169-171`).

That distinction holds in the admitted roots themselves:

- `S25` uses `R25`, `role_class: review`, `artifact_type: QA report and test verdict`, and
  `score_profile: "review, QA"` (`Scenarios-v2/S25-qa-verification-verdict/scenario.yaml:1-14`).
  Its README says the candidate does not patch code, redesign the feature, or review architecture
  and that the only editable surface is a QA verdict report
  (`Scenarios-v2/S25-qa-verification-verdict/README.md:4-5`, `:16`).
- `S33` uses `A02`, `role_class: adapter`, `artifact_type: transport execution report`, and
  `score_profile: adapters` (`Scenarios-v2/S33-external-reviewer-transport-fidelity/scenario.yaml:1-16`).
  Its README says transport fidelity only is scored and explicitly excludes semantic reviewer
  findings, QA verdicts, and remediation advice
  (`Scenarios-v2/S33-external-reviewer-transport-fidelity/README.md:3-6`, `:33`, `:42`).

The accepted integration memo reaches the same conclusion and addresses the only likely confusion
point: `S33` names an assigned internal reviewer role, but keeps the scored work transport-only
rather than semantic review evidence
(`Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-integration-2026-04-17.md:116-130`).

### 6. Blast radius remains additive and local without taxonomy or scoring drift into protected surfaces

Architecturally, the change surface is narrow and local:

- every admitted root is a new sibling under `Scenarios-v2/`
- each `scenario.yaml` restricts edits to bundle-local candidate files only
- none of the seven roots asks the candidate to modify shared scoring, taxonomy, publication, or
  first-wave surfaces

The accepted integration memo records that protected-surface isolation is supportable under the
accepted scope and explicitly treats the wave-2 planning memo as accepted upstream context and
`PLAN.md` as unrelated pre-existing untracked context
(`Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-integration-2026-04-17.md:132-189`).
The accepted QA memo independently records additive isolation to the seven roots plus the same
scope treatment for the upstream planning memo and `PLAN.md`
(`Work/next-upgraded-pack/Evidence/second-wave-scenario-materialization-qa-2026-04-17.md:126-158`).

I found no supported evidence that the second-wave materialization reopens taxonomy, modifies score
mapping, or drags protected control-plane surfaces into the live bundle contract. The visible
`score_profile` values on the seven roots stay within the admitted categories rather than
introducing new profile labels (`Scenarios-v2/S03-consultant-tradeoff-memo/scenario.yaml:14-15`,
`Scenarios-v2/S06-analyst-repository-fact-memo/scenario.yaml:15-16`,
`Scenarios-v2/S10-algorithm-invariant-proof-memo/scenario.yaml:14-15`,
`Scenarios-v2/S16-frontend-web-ui-patch/scenario.yaml:22-24`,
`Scenarios-v2/S17-qt-desktop-ui-patch/scenario.yaml:18-19`,
`Scenarios-v2/S25-qa-verification-verdict/scenario.yaml:13-14`,
`Scenarios-v2/S33-external-reviewer-transport-fidelity/scenario.yaml:14-16`).

## Findings

No blocking deviations.

No `REVISE` routes are required for implementer, `$architect`, or `$planner`.

## Maintainability notes

- The wave stays understandable because each bundle uses one primary role contract, one editable
  candidate surface, and one local verifier family. That keeps downstream reasoning local instead
  of coupling the seven roots through shared mutable control-plane files.
- `S06` and `S33` are the two bundles most likely to confuse future readers because one contains a
  noisy repo snapshot and the other names an assigned internal reviewer role. In both cases the
  bundle contracts keep the complexity bounded: `S06` makes the snapshot read-only evidence, and
  `S33` keeps provenance/transport separate from semantic review.

## Residual debt risk

Low within the admitted scope. The present wave adds benchmark breadth and a sharper role split,
but it does not materially increase shared-abstraction debt or dependency-direction risk because
the added surfaces remain bundle-local and additive.

## Gate decision

`PASS` - the architecture/cohesion gate is fully supported for the admitted second-wave scenario
materialization.

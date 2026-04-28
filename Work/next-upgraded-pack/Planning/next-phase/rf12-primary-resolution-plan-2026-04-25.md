Date: 2026-04-25
Owner: `$lead`
Status: `ACTIVE`

## Purpose

Resolve the remaining undefined `RF12+1 Short-Rule Table` primaries without extending the same
compact-vs-staged axis indefinitely.

Current canonical source: `Results-drafts/full-v2-hard-results-current.md`.
Current format alias: `RF12+1 Short-Rule Table` / `RF12`.

2026-04-28 continuation contract: use this file as the accepted roadmap -> design -> plan surface
for `N79+` hardening. Do not create a competing roadmap for the same X1/X3 separation work.
`hardening-wave-roadmap-2026-04-22.md` remains the live wave queue; this file defines why the
next N scenarios exist and how they are admitted.

External advisory check:

| Field | Value |
|---|---|
| Requested provider | Claude / Opus 4.7 max |
| Actual execution path | direct `claude -p --model opus --effort max --permission-mode bypassPermissions` |
| CLI provenance | PATH-resolved `claude.exe`, Claude Code `2.1.119`; absolute user-local path intentionally not recorded |
| Pack consultant mode | global `~/.codex/.agents-mode.yaml` has `consultantMode: disabled`; this was a direct provider consult by explicit user request, not a `$consultant` role artifact |

## Current Diagnosis

`X1 / gpt-5.5` and `X3 / opus 4.7max` remain tied globally at `35 / 40`, but their failure classes
are symmetric:

| Row | Fails | Failure class |
|---|---|---|
| `X1` | `N47`, `N48`, `N56`, `N57`, `N58` | hidden semantics/physics/scope pass, visible operator-output budget fails |
| `X3` | `N35`, `N36`, `N37`, `N39`, `N40` | staged re-entry, migration ledger, source binding, owner continuity, or closure semantics fail |

Opus advisory conclusion: this symmetry is useful, but risky. It may partly encode two prompt/style
signatures (`compact single-shot` versus `staged closure`) rather than independent role skill. Do not
add more same-axis probes until frame-inversion is checked.

## RF12 Resolution Policy

| Line | Current state | Policy |
|---|---|---|
| `L00 owner/control` | split | keep split; validate with frame-inversion only |
| `L01 advisory.repo-understanding` | near-tie | keep near-tie unless evidence-conflict wave produces stable separation |
| `L02 advisory.design-adr` | split | keep split; staged ADR already has N37 |
| `L03 design.ui-ux-structure` | near-tie | keep near-tie unless an objective visual/UX invariant appears |
| `L04 worker.reasoning-constraints` | split | keep split; science correctness is near-tie, compact science/runtime is X3 |
| `L05 worker.default-implementation` | split | keep split; staged migration X1, compact migration X3 |
| `L06 systems/performance-worker` | split | keep split; staged recovery X1, compact hot path X3 |
| `L07 worker.ui-implementation` | `X3` | no immediate work |
| `L08 worker.visual/graphics` | `X3` plus X1 diagnostic pixel edge | extend only through semantic visual correctness, not more compact-output probes |
| `L09 review.pre-pr` | split | keep split; ordinary tuple review near-tie, staged source-bound review X1 |
| `L10 review.security` | near-tie | high-priority unresolved line |
| `L11 review.performance-architecture` | `X1` staged, near-tie single-shot | no immediate work unless single-shot review must be split |
| `L12 review.ui-visual-correctness` | near-tie | high-priority unresolved line |

## Proposed Waves

| Wave | Target | Goal | Scoreable gate |
|---|---|---|---|
| `W41` frame-inversion audit | existing split axes | Detect whether current splits are prompt-frame/style-coded | Run two mirrored probes: compact wording over staged hidden requirements and staged wording over compact operator-budget requirements. If primary flips by wording alone, mark affected split as style-sensitive and do not promote it as hard role policy. |
| `W42` security depth gauntlet | `L10` | Try to assign a real primary for security review | Seed one realistic diff with 8-10 exact vuln tuples and false-positive traps. PASS requires exact issue id, severity, source location, owning boundary, and fix direction for a threshold set; FAIL for misses or false positives. |
| `W43` visual correctness gauntlet | `L12` and secondary `L08` | Separate semantic visual review from compact visual patching and pure pixel localization | Multi-breakpoint screenshot/DOM/CSS packet with seeded visual regressions. PASS requires exact element, state, breakpoint, and defect class; FAIL for wrong element/state or insufficient findings. |
| `W44` conflicting evidence discipline | `L01`, secondary `L02` | Probe repo-understanding beyond source recitation | Repo snapshot with current code, stale README, two conflicting ADRs, and a partial migration note. PASS requires surfacing the conflict, ranking sources, naming assumptions/non-claims, and choosing a bounded next action. |
| `W45` cross-phase integration owner | `L00`, `L09`, worker boundary | Cover governance rule not fully exercised by current 40-slot surface | Three-phase artifact chain with one subtle incompatibility before QA. PASS requires assigning integration owner, detecting cross-phase incompatibility before QA, and preserving repair/re-entry ledger. |

## Priority

| Priority | Wave | Reason |
|---|---|---|
| `P0` | `W41` | Validates whether current split evidence is skill-grounded or mostly prompt-frame-coded. |
| `P0` | `W42` | `L10` is the cleanest remaining near-tie with enumerable ground truth. |
| `P0` | `W43` | `L12` is unresolved and can be made objective through seeded screenshot/DOM defects. |
| `P1` | `W44` | Useful only if we still need a repo-understanding primary; otherwise near-tie is honest. |
| `P1` | `W45` | Valuable governance coverage, but likely reinforces staged X1 rather than creating a new axis. |

## Acceptance Rules

| Rule | Requirement |
|---|---|
| no style-only promotion | Do not promote a primary if the result changes under frame-inversion without a semantic miss. |
| no output-budget-only claims for near-tie lines | `L10` and `L12` must be scored by seeded objective misses/false positives, not by response length. |
| binary before rubric | A new primary needs scoreable PASS/FAIL separation or two independent rubric margins on the same lane. |
| calibration | Run `X2` and `X6` after a wave is stable; run `X5` only if route/runtime health is verified. |
| denominator discipline | New diagnostics stay outside `/40` until they replace a specific weak or near-tie slot with a documented promotion reason. |

## Recommended Next Action

Start with `W41` design as a short audit bundle. If frame-inversion passes, launch `W42` and `W43`
as the next primary-resolution waves. If frame-inversion fails, revise the RF12 report to mark the
affected split lines as `style-sensitive` instead of hard role policy.

Gate decision: `PASS` for planning.

## W41 Results

W41 was implemented as two frame-inversion diagnostics:

| Scenario | Frame inversion | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration |
|---|---|---|---|---|
| `N62` | compact prompt over N35-class staged interface requirements | `PASS` | `PASS` | `X2 FAIL` on exact scope; `X6 NOT-RUN` runtime timeout |
| `N63` | staged prompt over N57-class compact API migration plus operator budget | `FAIL` | `PASS` | `X2 FAIL` on operator budget; `X6 NOT-RUN` runtime timeout |

`N62` means X3 can satisfy the N35-class migration semantics when the work is a compact single-pass
task. The original N35/N36 split should therefore be read as staged re-entry / multi-session
accountability, not as a general inability to perform interface/API migration.

`N63` means X1 still violates the visible `40000` byte operator budget even when the task is framed
as staged work: `545831 > 40000` bytes. X3 passes the same gate at `3190` bytes. This confirms that
the compact low-noise separator is not just compact prompt wording.

Decision: keep RF12 primaries execution-shape-specific rather than claiming a single global
implementation winner. Next priority remains `W42` security depth and `W43` visual correctness,
because `L10` and `L12` still need objective primary-resolution evidence.

## W42 / W43 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W42` | `N64 security-depth review` | `PASS` | `PASS` | `X2 FAIL`; `X6` runtime-caveat `NOT-RUN` despite local verifier pass | `binary tie remains`; keep `L10` near-tie for ordinary security review |
| `W43` | `N65 visual-correctness review` | `PASS` | `PASS` | `X2 FAIL`; `X6 NOT-RUN` timeout before worker output | `binary tie remains`; keep `L12` near-tie for ordinary visual review |
| `W44` | `N66 conflicting-evidence memo` | `PASS` | `PASS` | `X2 FAIL`; `X6 FAIL` | `binary tie remains`; keep `L01` near-tie for conflicting-evidence repo-understanding |

Decision: W42, W43, and W44 are negative primary-resolution evidence. Exact tuple gates removed
compliance-retelling, and N66 separates lower calibration rows, but ordinary single-shot security
review, visual-correctness review, and conflicting-evidence repo-understanding still do not separate
`X1` from `X3`. Do not promote these diagnostics into the `full-v2-hard` `/40` denominator. Further
work should use a qualitatively different surface: cross-phase integration-owner `W45`, real repo
visual-review with actual screenshots, or a scored time/cost/patch-quality task where the metric is
itself role-relevant rather than incidental.

## W45 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W45` | `N67 cross-phase integration owner` | `PASS` | scoreable `FAIL`; wrapper `0`; missed pre-QA compatibility, QA-stop, repair/re-entry, and closure markers | `X2 FAIL`; `X6` runtime-caveat `NOT-RUN` with verifier failures | staged integration-owner / QA-gate packets are `X1 primary` |

Decision: W45 is a positive staged-governance separator, not a new compact-vs-staged style repeat.
It exercises a concrete role duty: detect cross-phase incompatibility before QA, assign the
integration owner, stop QA, and preserve repair/re-entry closure. Do not merge it into the
`full-v2-hard` `/40` denominator without a slot-replacement decision, but do update RF12 routing:
cross-phase integration-owner work goes to `X1`; compact single-session slices remain `X3`-eligible.

## W46 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W46` | `N68 actual screenshot visual review` | scoreable `FAIL`; `70 / 100` | scoreable `FAIL`; `80 / 100` | `X6 FAIL 20`; `X2 NOT-RUN`; `X5` smoke timeout | no binary winner; X3 gets scored actual-screenshot grounding edge |

Decision: W46 does not promote a visual-review primary by binary. It does add useful counter-evidence
to the N61 pure-pixel diagnostic: when the visual task is an actual screenshot review rather than tiny
square localization, X3 scores higher than X1, though neither passes the strict gate. Keep `L12`
ordinary visual review as near-tie after N65. For screenshot-first coordinate review, prefer X3
provisionally and verify.

## W47 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W47` | `N69 real-repo patch quality` | `PASS`; `85 / 100`; hidden ledger semantics and exact required paths pass; output-cost score `0` | `PASS`; `90 / 100`; hidden ledger semantics pass; low output cost; auxiliary cache churn lowers patch score | `X2 FAIL 35`; `X6 FAIL 35`; `X5` smoke timed out after `244s` with no output | `binary tie remains`; X3 has scored cost edge, X1 has patch-hygiene edge |

Decision: W47 does not create a binary top-pair primary because both top rows pass hidden correctness
and runtime. It is useful role-fit evidence for real-repo patch scoring: X3 remains favored when
operator cost is a first-class metric, while X1 is safer when exact workspace hygiene and no auxiliary
churn matter. Do not merge N69 into the `/40` denominator without a slot-replacement decision or a
same-lane repeat that makes the cost-vs-hygiene split policy-relevant.

## W48 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W48` | `N70 entitlement event migration` | `PASS`; `85 / 100`; hidden schema-v2 migration semantics and exact four-file patch pass; output-cost score `0` | `PASS`; `90 / 100`; hidden schema-v2 migration semantics pass; low output cost; auxiliary cache churn lowers patch score | `X2 FAIL 15`; `X6 NOT-RUN` runtime-wrapper after Gemini capacity/tool-loop noise | `binary tie remains`; X3 has scored cost edge, X1 has patch-hygiene edge |

Decision: W48 is a negative semantic separator result. Making the task multi-file with hidden
schema-v2 consumers still did not split the top pair by correctness. It independently repeats W47's
cost-vs-hygiene split, so the next wave should change axis: either real UI/browser execution, true
staged repair with persisted state, or a repo patch where hidden tests require modifying callers
rather than only pipeline internals.

## W49 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W49` | `N71 test-led rate-limit regression` | `PASS`; `83 / 100`; hidden behavior and required regression test pass; cost partial; auxiliary churn | `PASS`; `90 / 100`; hidden behavior and required regression test pass; low output cost; auxiliary churn | `X2 FAIL 15`; `X6 FAIL 15` | `binary tie remains`; X3 has scored cost edge |

Decision: the small test-led regression hypothesis did not produce an X1 binary edge. Both top rows
can satisfy behavior plus required regression-test artifact. Do not promote N71 into `/40`; use it as
negative evidence against "test-led patch" being enough by itself. If testing is the axis, the next
task must require deeper test strategy, multiple failure modes, or caller-spanning fixtures rather
than a single new regression file.

## W50 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W50` | `N72 caller-spanning API refactor` | `PASS`; `83 / 100`; hidden API/service/CLI/report callers pass; cost partial; auxiliary churn | `PASS`; `90 / 100`; hidden API/service/CLI/report callers pass; low output cost; auxiliary churn | `X2 FAIL 15`; `X6 NOT-RUN` no-summary timeout with local partial-run verifier fail; `X5` smoke timeout | `binary tie remains`; X3 has scored cost edge |

Decision: caller-spanning hidden tests did not create an X1 semantic edge in compact single-session
form. This reinforces the execution-shape split: staged API/interface migration remains `X1 primary`
from N35/N36, while ordinary single-session caller-spanning refactors are `X1 / X3 binary near-tie`
with X3 preferred when output cost matters and cache/scope hygiene is explicitly guarded.

## W51 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W51` | `N73 DOM event runtime UI` | `PASS`; `93 / 100`; filter, keyboard dirty, save, scope, and ledger pass | `PASS`; `93 / 100`; same runtime gates pass; much smaller output but slower elapsed proxy | `X2 FAIL 15`; `X6 FAIL 15` | `binary tie remains`; runtime UI correctness has no top-pair winner |

Decision: adding a deterministic DOM/event runtime harness did not separate `X1` and `X3`. Keep X3
primary for compact UI implementation only when low-noise/output budget is itself a hard gate
(N47/N60 evidence). For runtime UI correctness without strict output budget, keep `X1 / X3` as a
binary near-tie and verify behavior on the target UI.

## W52 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W52` | `N74 DOM runtime output budget` | scoreable `FAIL`; `80 / 100`; DOM runtime, exact scope, and ledger pass, but output budget fails at `241980` bytes | `PASS`; `100 / 100`; DOM runtime, exact scope, ledger, and `50000` byte output budget pass at `2085` bytes | not launched in W52; W51 just calibrated X2/X6 on the same DOM runtime base | compact inverse separator; X3 primary when runtime UI includes hard output budget |

Decision: N74 resolves the W51 ambiguity by making visible operator output a hard verifier rather
than a secondary rubric component. Runtime UI correctness remains near-tie without that budget, but
runtime UI plus strict low-noise operator contract is now an admitted X3-over-X1 diagnostic.

## W53 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W53` | `N75 persisted-state replay migration` | `PASS`; `83 / 100`; v1/v2 migration, immutability, idempotent replay, rollback, persist/load, scope, ledger, and visible regression pass | `PASS`; `83 / 100`; same semantic gates pass, much smaller output but slower elapsed proxy | `X2 PASS 75`; `X6 NOT-RUN` no-summary timeout | `binary tie remains`; single-session persisted-state migration is not a separator |

Decision: N75 is useful negative evidence. A hidden replay/rollback oracle alone is still too easy:
X1, X3, and X2 all pass semantically. The next persisted-state attempt should be staged across
failure intake, migration design, implementation, replay audit, repair/re-entry, and closeout, or it
should use a real repo fixture with stricter operability constraints.

## W54 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W54` | `N76 staged persisted-state reentry` | `PASS`; `85 / 100`; staged source, implementation, re-entry, closeout, and runtime verifier pass | scoreable `FAIL`; `15 / 100`; missing `migrator.py` scope, schema version, persist envelope, source/migration/reentry/closeout contracts | `X2 FAIL 70`; `X6 NOT-RUN` timeout/no-summary | X1 primary for staged persisted-state migration/re-entry |

Decision: W54 converts the weak N75 single-session fixture into a useful staged separator. This
matches the broader execution-shape rule: compact single-session implementation can tie or favor
X3, but staged re-entry with source accountability, runtime validation status, and closeout is
X1-primary.

## W55 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W55` | `N77 security capability runtime patch` | `PASS`; `85 / 100`; HMAC capability-token, binding, replay, redirect, audit, test, ledger, and exact-scope gates pass; output-cost score `0` | `PASS`; `93 / 100`; same security gates pass with low output cost; auxiliary cache churn lowers artifact score | `X2 FAIL 15`; `X6 NOT-RUN` no-summary timeout | `binary tie remains`; single-session security implementation has no semantic top-pair primary |

Decision: W55 closes the hypothesis that "runtime exploit security patch" alone would separate
X1/X3 in a compact single-session frame. It does not. The useful next security probe is a staged
security re-entry packet with source ledger, threat model, implementation, exploit validation,
regression closeout, and re-entry state.

## W56 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W56` | `N78 staged security re-entry` | `PASS`; `85 / 100`; staged threat ledger, implementation, exploit validation, re-entry, closeout, and hidden runtime security gates pass | scoreable `FAIL`; `23 / 100`; percent-encoded CRLF redirect trap plus staged ledger/validation/closeout gaps | `X2 FAIL 45`; `X6 NOT-RUN` no-summary timeout | X1 primary for staged security re-entry |

Decision: W56 confirms the execution-shape rule on the security lane. Single-session exploit patching
is near-tie after N77; staged security re-entry is X1-primary after N78. No Sonnet route was involved
in this result: current X3 runner config and summary label are `opus 4.7max` with `--effort max`.

## 2026-04-28 N79+ Roadmap

This queue is for new N scenarios only where they test a new unresolved axis. It is not a license to
keep adding minor variants to a solved compact-output or staged-ledger family.

| Priority | Wave | Scenario | Target RF line | Why this exists |
|---|---|---|---|---|
| `P0` | `W57` | `N79-staged-ui-visual-state-reentry-v2` | `L03`, `L07`, `L12` | Replace brittle `N38` with a bounded staged UI/visual-state packet that can produce scoreable X1/X3 evidence instead of no-summary runtime noise. |
| `P0` | `W58` | `N80-screenshot-grounding-review-v2` | `L12`, secondary `L08` | Convert the current actual-screenshot diagnostic into a calibrated visual-review task with pixel windows, semantic defect tuples, and false-positive traps. |
| `P1` | `W59` | `N81-evidence-conflict-repo-action-plan` | `L01`, secondary `L02` | Test repository understanding under stale docs, changed code, failing command evidence, and non-claim discipline instead of prose confidence. |
| `P1` | `W60` | `N82-ux-structure-runtime-state-spec` | `L03` | Make UX design objectively scoreable through state transitions, breakpoint invariants, copy/affordance ownership, and forbidden visual cues. |
| `P1` | `W61` | `N83-interface-refactor-breakage-hunt` | `L05`, `L09` | Re-test interface refactor quality through hidden consumer breakage and caller contract preservation, not output budget. |
| `P2` | `W62` | `N84-security-review-repro-gauntlet` | `L10` | Try to split ordinary security review with exploit reproduction evidence, exact vulnerability tuples, and false-positive suppression. |
| `P2` | `W63` | `N85-performance-review-runtime-budget` | `L06`, `L11` | Test performance role fit through measured hot-path improvement, profiler evidence, and semantic drift checks. |
| `P2` | `W64` | `N86-final-promotion-candidate-sweep` | `/40` slot policy | Decide which diagnostics, if any, replace weaker full-v2-hard slots before final X4 or lower-row comparison. |

## 2026-04-28 Design Contract

| Design rule | Required effect |
|---|---|
| new axis only | Every new N must state which unresolved RF line it targets and why previous evidence is insufficient. |
| scoreable before persuasive | PASS/FAIL must come from oracle/scorer/verifier output, not narrative judgment or stdout noise. |
| bounded staged tasks | Staged scenarios must keep phases short enough to avoid no-summary failures and must require exact source, implementation, re-entry, and closeout artifacts. |
| visual tasks use real visual evidence | Visual/UI-review scenarios must include screenshots or rendered artifacts, calibrated coordinate tolerance, semantic defect tuples, and false-positive traps. |
| no budget-only promotion | Operator-output budget can remain a diagnostic axis, but a new primary claim needs semantic/runtime evidence unless the lane explicitly owns low-noise operation. |
| no Gemini dependency | `X5` and `X6` stay parked while route/auth health is broken or deprioritized. They are calibration rows only after a completed wave. |
| X4 final only | `X4` stays out of iterative hardening. Run it only on final lanes when explicitly approved by the user. |
| canonical `/40` discipline | New diagnostics do not enter `full-v2-hard /40` until a slot-replacement decision names the removed slot and why the replacement is stronger. |

## 2026-04-28 Delivery Plan

| Phase | Scope | Acceptance gate | Checks |
|---|---|---|---|
| `A` plan alignment | Update this plan, live wave roadmap, and status checkpoint to make `N79+` the active route. | `PASS` when all three surfaces agree on `X1/X3 first`, Gemini parked, and X4 final-only. | `git diff --check`; doc self-consistency read. |
| `B` N79 materialization | Build bounded staged UI/visual-state re-entry v2. No changes to existing anchored rows. | `PASS` on 2026-04-28; bundle-shape, scorer syntax, expected start-state, and synthesized candidate dry-run passed. | JSON parse; `--bundle-shape-only`; synthesized dry-run; `git diff --check`. |
| `C` N79 run | Run `X1` and `X3` only. | `PASS` on 2026-04-28; both rows scoreable. `X1 PASS 96`; `X3 FAIL 63`. | Read `summary.json`, verifier logs, scorer JSON; update live evidence. |
| `D` N80 materialization | Build calibrated screenshot-grounding visual review v2. | `PASS` on 2026-04-28; nonzero `22 px` window, false-positive traps, threshold scorer, start-state fail, and reference PASS validated. | Image/oracle validation; local scorer probe; `git diff --check`. |
| `E` N80 run | Run `X1` and `X3` only. | `PASS` on 2026-04-28; `X1 PASS 82`, `X3 FAIL 63`, both wrapper `0`. | Same as phase `C`. |
| `F` N81 repo evidence-conflict/action-plan | Run the next advisory repo-understanding separator attempt after N79/N80. | `PASS` on 2026-04-28 as a completed wave; `X1 PASS 100`, `X3 PASS 100`, so `binary tie remains` and no primary is assigned. | JSON parse; `--bundle-shape-only`; expected start-state fail; synthesized reference PASS; `git diff --check`; `mcp-free`; top-pair run. |
| `F2` N82 UX runtime-state spec | Run the objective UX-structure state-spec separator attempt after N81. | `PASS` on 2026-04-28 as a completed wave; `X1 PASS 100`, `X3 PASS 100`, so `binary tie remains` and no primary is assigned. | JSON parse; `--bundle-shape-only`; expected start-state fail; synthesized reference PASS; `git diff --check`; `mcp-free`; top-pair run. |
| `F3` next P1 wave | Pick `N83` or a stronger UX runtime/visual simulation based on N82. | `NEXT`; current best next axis is `N83-interface-refactor-breakage-hunt` because N81/N82 show single-shot term anchors are weak separators. | Pre-run protocol plus live evidence update. |
| `G` promotion review | Decide whether any N79+ diagnostic replaces a weaker `/40` slot. | `PASS` only if the replacement has clearer role-fit value, stable scoring, and a named outgoing slot. | Update `full-v2-hard-results-current.md`, RF12, checkpoint, and evidence in one batch. |

## 2026-04-28 Gate Decision

`PASS`: N79+ roadmap/design/plan is admitted. Next concrete action is Phase `B`:
materialize `N79-staged-ui-visual-state-reentry-v2` and run `X1`/`X3` first.

## W57 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W57` | `N79 staged UI visual-state reentry v2` | `PASS`; `96 / 100`; hidden UI state, accessibility, layout, raster, ledger, closure, tests, scope, and phase-path gates pass | scoreable `FAIL`; `63 / 100`; visible blocked cue, focus-return id, active descendant/accessibility, compact layout containment, raster overlay order, and ledger/closure completeness fail | not launched by policy; `X4` final-only and Gemini parked | X1 primary for staged UI/visual-state reentry |

Decision: W57 replaces the unresolved `N38` staged UI branch with scoreable top-pair evidence. The
failure is not route/runtime noise: both wrappers exited `0`, both rows completed four phases, and
X3 passed exact scope plus phase-path discipline before failing the hidden UI/visual-state verifier.
This changes staged UI/visual-state routing to `X1 primary`. Compact single-session UI remains
X3-primary only when low-noise/output budget is part of the role contract.

Next concrete action: Phase `D`, materialize `N80-screenshot-grounding-review-v2`.

## W58 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W58` | `N80 screenshot-grounding review v2` | `PASS`; `82 / 100`; `8 / 10` matched, mean/max error `2.855 / 7.071 px`, no false positives | scoreable `FAIL`; `63 / 100`; `7 / 10` matched, mean/max error `8.067 / 17.117 px`, one false-positive header ornament | not launched by policy; `X4` final-only and Gemini parked | X1 primary for calibrated actual screenshot grounding |

Decision: W58 supersedes the non-binary N68 screenshot read for calibrated screenshot grounding. N68
still records that a loose strict-all-defects screenshot review gave X3 a scored non-binary edge, but
N80 is the better separator because it uses deterministic image generation, a nonzero coordinate
window, semantic defect tuples, false-positive traps, and a pass threshold. Both wrappers exited `0`,
so X3's failure is scoreable.

Completed follow-up: Phase `F` materialized and ran `N81-evidence-conflict-repo-action-plan`.

## W59 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W59` | `N81 evidence-conflict repo action plan` | `PASS`; `100 / 100`; `24 / 24` matched; exact changed path `candidate/action-plan.md` | `PASS`; `100 / 100`; `24 / 24` matched; exact changed path `candidate/action-plan.md` | not launched by policy; `X4` final-only and Gemini parked | `binary tie remains`; repo-understanding/action-plan stays near-tie |

Decision: W59 does not separate X1/X3. It is useful negative evidence: a stricter single-shot
source-authority/action-plan table is still solved by both top rows. The X3 worker also called out a
substring-gaming weakness in literal forbidden-snippet checks, so the next advisory hardening should
use decision-context or staged review gates rather than another broad literal trap.

Next concrete action: Phase `F2`, materialize `N82-ux-structure-runtime-state-spec` unless the manual
priority switches to `N83-interface-refactor-breakage-hunt`.

## W60 Results

| Wave | Scenario | `X1 / gpt-5.5` | `X3 / opus 4.7max` | Calibration | Decision |
|---|---|---|---|---|---|
| `W60` | `N82 UX runtime state spec` | `PASS`; `100 / 100`; `27 / 27` matched; exact changed path `candidate/ux-state-spec.json` | `PASS`; `100 / 100`; `27 / 27` matched; exact changed path `candidate/ux-state-spec.json` | not launched by policy; `X4` final-only and Gemini parked | `binary tie remains`; UX structure/runtime-state stays near-tie |

Decision: W60 does not separate X1/X3. Making UX structure objective through JSON state, breakpoint,
affordance, copy, handoff, and non-goal anchors was still solved by both top rows. Do not keep
tightening this as a term-matched single-shot spec; switch to runtime simulation, staged UX review, or
interface breakage where failures are behavioral.

Next concrete action: Phase `F3`, materialize `N83-interface-refactor-breakage-hunt`.

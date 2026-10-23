# Review-loop methodology (provider-neutral)

Apply the shared **Assistance and owner-equivalent execution (binding)** contract. Working helpers remain preferred; a defective helper permits declared owner-equivalent execution with the same actual data, ownership, serialization, preimages, rollback, truthful provenance, independent readback and resource guarantees. No fabricated helper receipts or host-denial bypass.

Canonical DESIGN source for the autonomous parallel-review-loop. This reference is provider-neutral and is NOT installed into any runtime (per `shared/references/README.md`). Each production pack ships a thin RUNTIME binding that carries the operative rules: Claude → `agents/contracts/review-loop.md` (read by `/agents-review-loop`); Codex → `skills/review-loop/`. Keep this trunk free of pack-specific execution detail (no concrete dispatch APIs, wrapper paths, or CLI syntax); those live in the per-pack bindings.

## Purpose

Get **independent multi-angle convergence** on one written fix-design artifact BEFORE the change lands. It is distinct from the other review surfaces: not a single advisory opinion, not disjoint parallel helper lanes, not a post-implementation specialist chain — it is an autonomous, multi-round, same-artifact loop with anti-drift and Root receiving convergence before the next selected action.

## Admission and supported initial realization

Use review-loop for an explicit user loop/full-review request, materially competing owner/contract/seam solutions, unresolved coupling without one falsifying oracle, repeated review/fix failure or moving same-class manifestations, or newly evidenced complexity. Resolve missing factual premises first. A verified one-owner local cause, settled contract and one clear falsifying oracle may use the bounded exact-delta route when no mandatory trigger applies. Record the reason at the decision boundary; file count and `design-decision` alone do not mandate a loop. Before dispatch, select and freeze one supported initial route per fresh lane under current user constraints, effective policy and observed host/tools. Ordinary native/host dispatch is supported when external execution is not required; explicit external-only selection remains external-only. No route switch after a failed launch. Preserve exact-runtime requirements and record missing actual metadata as `unspecified by runtime`, never as observed requested/resolved controls. Two independent nonauthoring substantive contexts and one reconciled factual scout remain mandatory. Native lanes require actual terminal host results plus independent receiving checks and canonical terminal settlement/readback; external lanes preserve their existing adapter acceptance guarantees. State acceptance does not attest route provenance.

## The angles: two SMART verdicts + one mechanical SCOUT

Angles are defined by **SCOPE, not by vendor**. The FOCUS each is given is what makes it independent, so the same engine in two scopes is two distinct angles. Vendors are **symmetric**: any capable vendor can fill any scope; the vendor→scope mapping is a configurable per-pack default, not a hardcode.

| Angle | Role | Produces |
| --- | --- | --- |
| **Surgical correctness** | the specific defect, contract/seam violation, "this exact line/binding is wrong", visual-bug detection | a VERDICT (PASS/REVISE) |
| **Deep reasoning** | blast-radius, cross-system ripple, large-context synthesis, ADR / framing / "is this the right shape" / "what you're NOT doing" | a VERDICT (PASS/REVISE) |
| **Mechanical scout** | fully-specified scans: "does referenced X exist?", "list every reference to Y", sketch-vs-code, symbol/style — surfaces RAW findings + blind-spot hints | FINDINGS (no verdict) |

The **scout does not co-judge**: it executes spelled-out mechanical scans and surfaces raw facts/hints that FEED the two verdict angles and the synthesis. A scout finding is an INPUT to a verdict, not a verdict.

### Strength-aware default assignment (symmetric structure)
Per published model positioning + observed behavior (do not use context-window size as the differentiator for 1M-capable variants; the axis is depth-of-reasoning vs speed):
- **A surgery/visual-bug-strong engine** → the surgical-correctness verdict.
- **A sufficient policy-admissible reasoning profile for the actual task** → the deep-reasoning verdict; task-specific evidence, not a strongest-model default, justifies a costlier profile.
- **A fast/cheap engine** → the mechanical scout (reliable only for fully-specified tasks, or as a mindless broad scout that may surface a blind-spot hint; map it to a FACTUAL, non-judging role, never a judging one).
Each pack records its concrete engine→scope→role mapping in its binding. Accepted implementation preserves required guarantees, invariants, upstream claim identity, and genuine veto corrections; optional reviewer HOW or telemetry remains advisory/nonblocking unless separately admitted into scope. Utility execution grants no commit or publication authority: the root owns verified local checkpoints, and publication retains its human-review gate.

## Autonomous convergence + anti-drift

The orchestrator drives the loop to convergence **without a human gate per round or merely because convergence occurred**. Root receives the complete terminal outcome before the next selected action; real human, scope, pause and publication gates keep their dependent hold. Each round, while not yet converged and on course:
1. **Revise the artifact** — fold in EVERY open blocker from the verdict angles and every unreconciled scout finding (re-dispatching an unchanged artifact is forbidden — a verdict cannot change on identical input).
2. **Anti-drift check (mandatory, every round)** — verify the revised artifact still serves the ORIGINAL pinned objective: goal, admitted scope, and verified premises and their claim/evidence scope all unchanged. A revision that shifts the goal, widens scope, or rests on a new unverified premise is **drift** → stop and escalate; do not re-dispatch. Anti-drift is the course-keeper that replaces the human while the loop runs.
3. **Re-dispatch** the receipt-admitted angles on the revised artifact, carrying the ORIGINAL objective verbatim. Initial and full-artifact rounds admit all three angles; an eligible exact-delta correction round admits only its affected angles.

**Convergence** = both VERDICT angles PASS AND every scout finding is reconciled (none left dangling). Receive the terminal outcome through Root: present the accepted design and short round history, verify both verdicts, reconciled scout findings and canonical closure/readback, then continue the next already-authorized ready action under its existing gates. A design-only request ends at its accepted handoff; an actual human, scope, pause or publication gate holds only its dependent action. Drift or deadlock stops the affected loop and escalates its unresolved decision/cap; independent admitted ready work may continue. No human gate is added per round or merely because convergence occurred, and convergence creates no new execution authority.

For metadata-only reconciliation of a completed scout result, use `amend-scout-reconciliation --state <state> --operation-id <id> --round <current> --attempt-id <scout> --artifact-revision <revision> --metadata-file <json>`. The request contains exactly `version:1`, `scout_result_sha256` (lowercase SHA-256 of the entire original complete scout block under sorted-key compact JSON), required `expected_head` (explicit null initially, otherwise current operation ID), sorted complete `links` with `finding_index`/`reconciliation_index` into the immutable original arrays, and nonempty Root semantic comparison evidence inline or by accepted reference. Each genuine correction appends one immutable typed operation and advances `scout_reconciliation_amendment.operation_id`; superseded operations remain history and exact old replay never moves the head. Only the latest complete round's direct complete scout in a running loop is amendable. The same effective projection drives close and retained-origin validation. Original findings/dispositions, reviewed artifact, judgments, attempts, retries and caps do not change; this is no new review round or quality vote. Root verifies actual correspondence; evidence shape alone is not semantic proof. Existing frozen-artifact checks apply without a live-source or owner-selfhash requirement. The canonical write owner compares the prepared and committed serialized values before success; uncertainty preserves actual state for readback/replay. Older owners intentionally reject the optional round field; synchronize capable owner/readers before use. Actual helper execution alone emits the helper event. Declared manual-equivalent execution preserves the same logical transaction and uses `ORCHESTRARIUM_REVIEW_LOOP_STATE_V2_OWNER_EQUIVALENT_MANUAL`, `execution_path=owner-equivalent-manual` and truthful source evidence, never a fabricated helper receipt.

**Runaway guard:** cap at **N = 3** rounds; if not converged by round 3, stop and escalate the deadlock. Escalate EARLY if the same blocker survives unchanged across two rounds.

### Exact-delta correction rounds

The initial round and every full-artifact round run all three angles. After a correction, the orchestrator may admit a non-empty strict subset only when an accepted change classification identifies exactly the affected angles and every unaffected effective result from the immediately previous round remains valid for the corrected artifact: each retained verdict resolves to `PASS`, and a retained scout result is fully reconciled. Use a full-artifact round when the human requests one, a new defect class appears, the upstream artifact changes materially, or the affected-angle classification is unclear.

A retained angle is provenance to a previously completed effective result, not a fresh verdict, finding, or run. It has no new attempt ID and does not copy `PASS`, rationale, findings, or reconciliation into the new round. The orchestrator launches only the fresh attempt IDs in the committed admission, read back from actual canonical state; it must not synthesize an attempt or manually copy a prior result. Exact-delta selection is provider- and model-agnostic and changes neither the existing dispatched role and route-appropriate provenance requirements nor review authority, retry ownership and failure reconciliation, the three-round cap, or the absence of automatic continuous-integration enforcement.

**Model-mismatch trigger (a distinct escape the runaway cap misses).** The cap above catches a blocker that survives UNCHANGED. A different failure hides from it: the blocker MOVES — each round closes one manifestation and a new adjacent one appears (a "phase-graph chase"). That recurrence signals the MODEL is wrong, not that the last fix had a bug — a correctness loop, which only asks "is this fix correct?", cannot by construction name a model mismatch, so it chases the defect around the phase graph indefinitely. When the same defect CLASS reappears at a new spot across ~3 rounds, STOP correctness rounds and dispatch a MODEL-review lane (design/architecture angles, e.g. `architect` / `architecture-reviewer`) asked whether the mechanism/model is right or the chase is a model-mismatch symptom — fed the manifestation phase-graph (where the defect surfaced across rounds), not the latest diff — to name the right model or confirm the current one is at its honest documented-residual floor. Resume correctness rounds only after the model is confirmed or replaced. Per the `review-the-model-not-just-the-spec` precedent.

## Hardening invariants (every round)
Against false convergence (angles agreeing on a wrong-but-plausible result) and weak anti-drift:
1. **Verified premises are a hard gate, not a section.** Before admitting the loop, directly acquire primary evidence THIS session sufficient for each decision-driving claim, and name its owner and falsifying probe. A report, plan or commit message is a pointer, never proof of its asserted root. Verify the underlying evidence and causal chain for the exact claim; rule out material alternatives. Current text or Source inspection proves only the inspected wording or logic, not an actual runtime cause, measured value or target outcome. Runtime and target-environment claims require the corresponding actual observation and functional receiving. For a reported runtime-performance symptom, the FIRST action remains live profiling of the actual reported scenario. Unmeasured runtime values and other unresolved driving premises remain ASSUMPTION (UNVERIFIED), advisory, and hold their dependent loop/design/fix until resolved. Never pin a premise `CONFIRMED — do not re-litigate`.
2. **Every angle answers** "premises proven for these exact claims?", "scope unchanged?", "verification adequate?" — not only its scope.
3. **Reject bare PASS** — cite specific blockers (evidence/`file:line`) or a specific no-blocker rationale.
4. **Per-round diff** — record what changed and why (which blocker it answers).
5. **Verify actual terminal results, not notifications** — native lanes require actual terminal host output and independent receiving checks, settlement and readback; external manual equivalents preserve the shared assistance contract. For actual prompt-wrapper execution, count the lane only after its approved thin wrapper accepts the terminal result through the strict V2 parser, full external-nonauthorizing tuple, and untrusted/potentially-sensitive resultText contract. A completion signal from a sidecar (watcher / notifier / background-task callback / "task done" notification) is never a substitute for that return. A standalone watcher may observe only caller-managed background captures outside the prompt-wrapper path.
6. **Escalate early on a stuck blocker.**
7. **Failed lane is unverified.** Any expected lane that errors, dies, or hits a time/token/usage limit is UNVERIFIED. Record the failed attempt, re-dispatch that lane, and never infer a clean result from silence. Before convergence, reconcile expected lanes against substantive outputs and recorded failures; every failure must name the successful re-dispatch that supersedes it.
8. **Fail-closed aggregation.** A missing/null sub-verdict or findings payload is NOT-clean. An aggregation or gate remains `REVISE` and exits non-zero until every expected lane has substantive output and every recorded failure is reconciled.

## review-loop-state ledger (structural backstop)
The governed formal state path uses one serialized owner transaction, normally through its runtime helper or declared owner-equivalent execution under the shared assistance contract. The transaction freezes the artifact, atomically persists and reads back the admitted round. Actual helper execution then emits its committed receipt carrying fresh attempt IDs and the round artifact revision; a manual equivalent records real transaction provenance and the same canonical identity without impersonating that helper receipt. A correction-round receipt may also carry exact-delta coverage that binds the affected angles to the immediately previous round and revision; retained-angle provenance remains in the committed state. This binding is procedural, not an executable host-enforced dispatch gate. Provider bindings may add bounded dispatch-time observation, but the helper itself does not observe bypass; manual-equivalent transitions preserve the same data guarantees without claiming helper execution; unadmitted direct/ad-hoc launches remain outside its guarantees. The historical observer gap is fixed without expanding the helper's guarantees. Personal/operator-owned reviews remain outside this state path.

The state owner records pinned objective/scope/runtime-root anchors, ordered idempotent operations, and per-round phase, diff, frozen artifact identity, fresh attempts, retained references when applicable, failures, results, and evidence. Each admitted lane's failures form one append-only immediate-successor chain (`A → B → C`) ending at its current attempt: it has one root and tip, no branch, merge, cycle, cross-lane reuse, dangling/disconnected node, or historical unresolved failure, and at most three retry edges. Every result or failed attempt asserts the owning round's identity. Retry keeps that identity; a corrective edit creates a new round and a newly frozen identity. Missing outputs, unresolved failures, mismatched identity, changed snapshots, conflicting operation replay, or failed commit/read-back remain non-clean. A stable lock file carries an operating-system exclusive kernel lock; file presence is not ownership. Graceful cancellation cleans owned uncommitted resources. Hard termination cannot clean synchronously; the next lock-owning invocation reconciles only unreferenced engine-owned resources. Invalid or uncertain state returns `RLSTATE_RECOVERY_REQUIRED` without deleting candidate evidence. A repository-only structural validator exposes the same schema for development and continuous integration, but does not own a second copy of the rules and still cannot judge semantic soundness. The runtime-root anchor and root-proven question retain their compatibility names for verified premises; those names do not assert runtime measurement.

Existing V1 ledgers remain read-only; migration never guesses historical identity. Provider completion, work-item closure, scoped gate invalidation, and the operator-owned exception remain owned by their existing contracts.

## Terms and Abbreviations
- **angle**: one independent review lens (surgical / deep / mechanical-scout) in the loop.
- **scout**: the mechanical angle — surfaces raw findings, casts no verdict, feeds the verdict angles.
- **anti-drift**: the per-round check that the revised artifact still serves the original pinned objective.
- **convergence**: both verdict angles PASS and all scout findings reconciled.
- **ledger / review-loop-state**: the per-round persisted record that gives the autonomous loop an auditable structural backstop.

## Verdict closure is universal (decision 2026-07-16-review-verdict-closure)

The closure rule binds ANY commissioned review or audit — this loop, an ad-hoc council, an external
adapter audit, a design review — whether or not this methodology was invoked: **a returned `REVISE`
closes only on a re-verification `PASS` from that angle or a recorded equivalent; author belief or a
green mechanical validator never closes it** (the always-on spine carries this clause). Typed
dispositions are the only alternatives: `WAIVED:user` (user-authorized, evidence-carried; never legal
against protected or unclassified findings) and `WAIVED:security-reviewer` (completed, exact
target-bound `manual-check` evidence, with `role` or `assignedRole` equal to `security-reviewer`). For
TRACKED work-items the relation is mechanical: the wrapper-owner terminal-ledger protocol records
launch+terminal events, the closer names the exact `closesRunIds`, and `check-work-items-state` fails on open
obligations. Replacement-reviewer equivalence must preserve: the review scope, independence from the
author, the same evidence target/version, and an equal-or-stronger declared tier — recorded in
structured fields, not prose. Reviews outside any work-item remain governed by the spine clause alone
(declared residual).

**`HOW→VERIFY independence: VERIFY(F) owner/engine ≠ HOW(F) author`.** Independence lives on the HOW→VERIFY edge, not the WHAT→HOW edge: a reviewer may author a fix's HOW while context is fresh; only verification of the implemented fix must be independent. For an `inline-sufficient` finding, no separate fix-design/HOW-review pass is required before implementation, but loop-to-PASS re-verification remains mandatory. **Author-exclusion for design-class (`fix-class: design-decision`) fixes:** when the implemented fix of a `design-decision` finding followed a reviewer's authored HOW, at least one discharging verdict must come from an angle that did not author that HOW; a distinct scope counts as distinct even on the same engine. No non-authoring verifier means no clean `PASS`: leave the HOW advisory and report `UNVERIFIED`.

**Review a FROZEN artifact, never the live working tree (2026-07-17, live incident).** A verdict is a
statement about one artifact revision, so the thing under review must not move while the round runs:
dispatch at a committed revision, a `git diff` patch file, or a copied snapshot, and give the
reviewer its identity (sha or digests). An angle caught this gate's engine mid-edit — including a
transient syntax error — and correctly refused the patch: "the moving live target prevents accepting
that patch as the current implementation". If a finding forces an edit while a round is in flight,
that edit makes a NEW snapshot and a NEW round; it never mutates what the current round is judging.
Full lesson: `work-items/lessons/2026-07-17-review-a-frozen-snapshot-not-a-live-tree.md`.

**Ledger read-back before reporting a verdict (2026-07-17, live incident).** On a tracked item, a
lane's verdict may be reported or acted on ONLY after reading the ledger back and confirming the
terminal event exists for that launch `runId`. The wrapper result's `resultText` is evidence of what the
reviewer said, never evidence that the obligation moved. This is the polling-anchor discipline
applied to closure: anchor on the authoritative store, not on a self-derived signal. The incident
that forced the rule: a validator defect rejected terminal events whose artifact was a repository
file, the wrapper only WARNed, and TWO real `PASS` verdicts were reported to the operator from prose
while the ledger held nothing (`work-items/bugs/2026-07-17-validator-artifact-workitem-relative-only.md`).

**Close every open runId of the lane, not just the latest.** Each round's `REVISE` is its own
obligation, so a lane that went `REVISE → fix → REVISE → fix → PASS` needs the final closer to carry
`closesRunIds` for EVERY still-open runId of that lane. Closing only the most recent one silently
leaves the earlier obligations open — the checker will say so at the gate, which is the backstop, not
the plan.

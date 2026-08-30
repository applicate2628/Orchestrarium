---
name: review-loop
description: "Review loop: run parallel reviews on a fix design."
---

# Review Loop

Get independent multi-angle convergence on one written fix-design artifact BEFORE the change lands. Three scope angles (two SMART verdicts + one mechanical SCOUT) review the same artifact; the loop revises and re-dispatches autonomously under an anti-drift guard and gates the human only at convergence.

This is the Codex-line binding of the provider-neutral review-loop methodology. The design trunk (`shared/references/review-loop-methodology.md`) is NOT installed; this skill carries the operative rules for the Codex runtime.

## Workflow economy projection

Apply the binding shared **Workflow economy (binding)** rule: this loop starts only from its documented evidence trigger, never as default pre-implementation review. After a finding, re-dispatch only the exact open finding and its changed delta; start a full-artifact round only for a new defect class or material upstream revision.

## Codex execution model (NOT the Claude background-Agent loop)

No verdict angle runs in the session that authored or revises the artifact. The Codex-line default is **two fresh explicit external Codex processes**, one surgical and one deep: each uses `externalProvider: codex` with distinct attempt IDs, prompt files, and committed receipts. They are independent by **scope**, so distinct prompts and frozen artifacts remain required even though both use Codex. The default is never `auto` or Claude, and must not request `fast`, `priority`, or `ultrafast`; standard speed is the only allowed speed posture. This local review-loop binding deliberately overrides neither global `agents-mode` defaults nor the Claude-line binding.

- The angles are dispatched as external helper runs (per `$external-brigade` and `external-dispatch.md`), each carrying its scope and the pinned objective verbatim.
- Where the host runtime cannot launch a scope concurrently, run the angles **sequentially** and synthesize their outputs; sequential execution does not change the loop's logic, only its concurrency.
- Count an external angle only after the approved thin wrapper owner in `external-dispatch.md` accepts its terminal result through the strict V2 parser, full external-nonauthorizing tuple, and untrusted/potentially-sensitive resultText contract; a launch is not a verdict.
- Claude is allowed only through an explicitly user-selected approved API-key route, with its own fresh prompt and receipt; it is never a fallback for either default Codex verdict. Kimi may be explicitly selected for the deep/wide angle as read-only and nonauthorizing; a failed Kimi lane remains UNVERIFIED and must be re-dispatched or reported as such.

## The angles: two SMART verdicts + one mechanical SCOUT

Angles are defined by **SCOPE, not by vendor**. The FOCUS each is given makes it independent. This Codex binding assigns both default verdict scopes to separate explicit Codex external processes.

| Angle | Scope | Produces | Codex-line default |
| --- | --- | --- | --- |
| **Surgical correctness** | the specific defect, contract/seam violation, "this exact line/binding is wrong", visual-bug detection | a VERDICT (PASS/REVISE) | fresh external Codex, `externalProvider: codex` |
| **Deep reasoning** | blast-radius, cross-system ripple, large-context synthesis, ADR / framing / "is this the right shape" | a VERDICT (PASS/REVISE) | separately fresh external Codex, `externalProvider: codex`; explicit Kimi is an optional nonauthorizing replacement only |
| **Mechanical scout** | fully-specified scans: "does referenced X exist?", "list every reference to Y", sketch-vs-code, symbol/style | FINDINGS (no verdict) | strictly mechanical factual role; surfaces raw findings + blind-spot hints |

The **scout does not co-judge**: it executes spelled-out mechanical scans and surfaces raw facts that FEED the two verdict angles. A scout finding is an INPUT to a verdict, not a verdict. The scout maps to a FACTUAL, non-judging role, never a judging one.

## Steps

1. **Read the routing surface.** Read and normalize `.agents/.agents-mode.yaml` first for the applicable external contract, but do not let `auto`, priority profiles, or the Claude default route either verdict lane. Dispatch the two default verdicts explicitly as `externalProvider: codex`; Kimi stays explicit-only, Windows-enrolled, read-only, no-tools, independently verified, and nonauthorizing; Grok remains unavailable in 1.x.
2. **Confirm the runtime-verified root (hard gate).** The artifact's root must be runtime-captured THIS session. A second-hand root (commit message, prior plan, report) is runtime-verified first or the loop does not start. Never pin the root `CONFIRMED — do not re-litigate`.
3. **Write the fix-design artifact** under `.scratch/reviews/fix-design-YYYY-MM-DD-<topic>.md`: runtime-verified root with trace/`file:line` citations, candidate options with cost/risk, recommended option, implementation sketch, validation plan, and what each scope angle should evaluate.
4. **Use the state owner for the supported formal path.** Resolve the installed `review_loop_state.py` helper from project-local `.agents/skills/lead/scripts/` first, then `$HOME/.agents/skills/lead/scripts/`. Invoke `review_loop_state.py begin` with state below `.scratch/reviews/<loop-id>/`, file inputs for objective/scope/runtime-root/diff, and the artifact file or verified Git revision. Parse the single JSON receipt and require `event=ORCHESTRARIUM_REVIEW_LOOP_STATE_V2`. A non-zero exit, missing receipt, malformed receipt, or failed read-back stops this supported procedure; do not represent any output from a bypass as state-engine-governed.
5. **Dispatch all three angles** through the external surface using the attempt IDs and `artifact_revision` returned by that committed receipt, each with the ORIGINAL objective verbatim. Launch surgical and deep as distinct fresh explicit Codex processes, never `auto` and never Claude; write one separate prompt file per launch and use the matching receipt. Use file-based prompt delivery (argv stays for launcher flags and file paths), standard speed only, and run concurrently when the runtime supports it, else sequentially. Call `mark-running` immediately before each launch; a result/failure counts in this state record only after `record-result`/`record-failure` succeeds with the same round, attempt ID, and artifact revision.
6. **Converge autonomously through the state owner.** No human gate per round. Reconcile failures with `admit-retry`; finish a structurally clean round with `complete-round`. After a `REVISE`, revise the artifact, run the mandatory anti-drift check, and call `next-round` to freeze the new artifact before re-dispatch. Close only through `close --outcome converged|drift|deadlock`. Mutating commands use fresh operation IDs and replay the same ID only for an idempotent retry. When DEVELOPING this pack, the thin `scripts/validate-review-loop-state.py` entry point checks the same schema owner.
7. **Human gate at convergence only** — never per round: (a) converged (both verdict angles PASS + all scout findings reconciled); (b) drift (present what would shift off the pinned objective); (c) deadlock (cap N=3 reached).
8. **Implement after acceptance**, with every guard/invariant/instrumentation the angles named; run the validation plan and capture evidence before the commit gate.

## Autonomous convergence + anti-drift

- **Revise → anti-drift check → re-dispatch**, every round. Re-dispatching an unchanged artifact is forbidden (a verdict cannot change on identical input).
- **Anti-drift (mandatory):** the revised artifact must still serve the ORIGINAL pinned objective; a shift in goal, a widened scope, or a new unverified premise is drift → stop and escalate.
- **Convergence** = both VERDICT angles PASS AND every scout finding reconciled.
- **Runaway guard:** cap at **N = 3** rounds; escalate early if the same blocker survives two rounds.
- **Model-mismatch trigger:** the cap catches a blocker that stays UNCHANGED; it is blind to a blocker that MOVES — each round the fix closes one manifestation and a new adjacent one appears (a "phase-graph chase"). That recurrence signals the MODEL is wrong, not that the last fix had a bug, and a correctness loop cannot name a model mismatch. When the same defect CLASS reappears at a new spot across ~3 rounds, STOP correctness rounds and dispatch a MODEL-review lane (design/architecture angles — `$architect` / `$architecture-reviewer`, or the external-reviewer lane on the Codex line — asked "is the MECHANISM right, or is the chase a symptom of a model mismatch?" — fed the manifestation PHASE-GRAPH, not the latest diff, to name the right model or confirm the honest documented-residual floor). Resume correctness only after the model is confirmed or replaced. Per the `review-the-model-not-just-the-spec` precedent.

## Hardening invariants (every round)

The runtime gate explicitly enforces hardening invariants 7-8 (failed-lane-is-unverified, fail-closed aggregation); neither silence nor a null lane result can converge.

1. Runtime-evidence is a hard gate, not a section (root captured this session; never pinned `CONFIRMED`).
2. Every angle answers "root proven (runtime)?", "scope unchanged?", "verification adequate?" — not only its scope.
3. Reject bare `PASS` — cite specific blockers (`file:line` / evidence) or a specific no-blocker rationale.
4. Per-round diff — what changed and why (which blocker it answers).
5. Verify wrapper results, not launch acknowledgements. A completion signal from a *sidecar* (watcher / notifier / background-task callback / "task done" notification) is NOT a verdict on a prompt-wrapper run: count that run only after the approved thin wrapper owner accepts its terminal result through the strict V2 parser, full external-nonauthorizing tuple, and untrusted/potentially-sensitive resultText contract. A standalone watcher remains only for caller-managed background captures outside the prompt-wrapper path; never use it to replace the wrapper return.
6. Escalate early on a stuck blocker.
7. **Failed lane is unverified.** Any expected lane that errors, dies, or hits a time/token/usage limit is UNVERIFIED. Record the failed attempt, re-dispatch that lane, and never infer a clean result from silence. Before convergence, reconcile expected lanes against substantive outputs and recorded failures; every failure must name the successful re-dispatch that supersedes it.
8. **Fail-closed aggregation.** A missing/null sub-verdict or findings payload is NOT-clean. An aggregation or gate remains `REVISE` and exits non-zero until every expected lane has substantive output and every recorded failure is reconciled.

## review-loop-state ledger (structural backstop)

A shipped formal loop MUST use the installed `review_loop_state.py` transaction owner. Schema V2 records pinned objective/scope/runtime-root, ordered idempotent operations, and per-round diff, phase, frozen artifact identity, three current attempts, failed-attempt history, results, and evidence. For each lane, failure history is one append-only immediate-successor chain (`A → B → C`) with one root and current tip: no branch, merge, cycle, cross-lane reuse, dangling/disconnected node, or historical unresolved failure; at most three retry edges are allowed. The engine writes JSON below `.scratch/reviews/`, rejects path/link escapes and unknown fields, atomically replaces and reads back the state, and emits `ORCHESTRARIUM_REVIEW_LOOP_STATE_V2` only after the committed record validates. Every attempt and failure echoes the owning round's `artifact_revision`; a mismatch or changed snapshot fails without counting a result. A retry keeps the round identity; a corrective edit is admitted only as a new round with a newly frozen identity.

The helper is the supported `$review-loop` state path, not an executable host-enforced dispatch gate. It does not observe bypass, so direct/ad-hoc launches remain outside the engine's guarantees. The historical cross-pack observer gap is fixed; provider-specific observation does not expand this helper's guarantee. Personal/operator-owned reviews remain outside this state path. Mutations serialize through a stable lock file whose ownership is the operating system's exclusive kernel lock, not file presence. Graceful cancellation cleans owned uncommitted resources; hard process termination cannot run cleanup and is reconciled by the next lock-owning invocation. Invalid or uncertain committed state returns `RLSTATE_RECOVERY_REQUIRED` without deleting candidate evidence. V1 records remain readable by the development/CI validator with `RLSTATE_V1_READ_ONLY`; V1 mutation requires explicit migration with an authoritative revision for every round. The development validator remains repository-only and delegates to the same state owner rather than maintaining a second schema.

## Rules

- This is a utility skill, not a new specialist role, and not a replacement for `$lead`.
- The strategic/deep angle returns its verdict DIRECTLY; it is NOT the standalone external-mode `$consultant` (which shells out to its own provider — the role-confusion). `consultant` stays untouched.
- The mechanical scout casts no verdict; map it to a factual role, never a QA-gate role.
- Do not silently downgrade an external angle to internal execution.
- Do NOT commit, push, or install from this skill. Implementation stops at the human commit gate.

## Non-goals

- Not a single advisory opinion (that is `$second-opinion` / `$consultant`).
- Not disjoint parallel helper lanes that each own a different artifact (that is `$external-brigade`).
- Not a post-implementation specialist review chain.
- Not for trivial one-line changes, and not for a root that is still an unmeasured runtime value.

## Terms and Abbreviations

- **angle**: one independent review lens (surgical / deep / mechanical-scout) in the loop.
- **scout**: the mechanical angle — surfaces raw findings, casts no verdict, feeds the verdict angles.
- **anti-drift**: the per-round check that the revised artifact still serves the original pinned objective.
- **convergence**: both verdict angles PASS and all scout findings reconciled.
- **ledger / review-loop-state**: the per-round persisted record giving the autonomous loop an auditable structural backstop.
- **ADR**: Architecture Decision Record, a written record of a significant design decision and its rationale.
- **CLI**: Command-Line Interface, a terminal command surface such as `codex` or `claude`.
- **PASS / REVISE / BLOCKED**: gate verdicts — accept, return for bounded correction, or stop on a real external blocker.

## Verdict closure (binding form of decision 2026-07-16-review-verdict-closure)

- Every dispatched external angle on a TRACKED work-item uses the approved thin wrapper owned by
  `external-dispatch.md`. That owner supplies the strict V2 parser, full external-nonauthorizing
  tuple, untrusted/potentially-sensitive resultText handling, and terminal-ledger protocol; an
  angle cannot close a work-item directly or replace that protocol with manual ledger commands.
- **Loop-to-PASS is the gate, not a preference:** a lane's `REVISE` closes only when THAT lane (or a
  recorded equivalent, structured fields) re-verifies `PASS` naming the exact `closesRunIds`. Author
  belief, applied fixes, or a green mechanical validator never close it; `check-work-items-state`
  FAILs on open obligations by default and the root publication gate blocks on them.
- **`HOW→VERIFY independence: VERIFY(F) owner/engine ≠ HOW(F) author`.** Independence is a property of the HOW→VERIFY edge, not the WHAT→HOW edge: a reviewer may author a fix's HOW while context is fresh; only verification of the implemented fix must stay independent. For an `inline-sufficient` finding, no separate fix-design/HOW-review pass is required before implementation, but the existing loop-to-PASS re-verification remains mandatory. **Author-exclusion for design-class (`fix-class: design-decision`) fixes:** when the implemented fix of a `design-decision` finding followed a reviewer's authored HOW, at least one discharging verdict MUST come from an angle that did not author that HOW. A distinct scope counts as distinct even on the same engine (see `## The angles`); this is stronger than the same-angle re-verification that suffices for `inline-sufficient` findings. No non-authoring verifier means no clean `PASS`: leave the HOW advisory and report the gap as `UNVERIFIED`.
- **Review a FROZEN artifact, never the live working tree (2026-07-17, live incident).** A verdict is a statement about one artifact revision, so the thing under review must not move while the round runs: dispatch at a committed revision, a `git diff` patch file, or a copied snapshot, and give the reviewer its identity (sha or digest). An angle caught this gate's engine mid-edit — including a transient syntax error — and correctly refused the patch: "the moving live target prevents accepting that patch as the current implementation". If a finding forces an edit while a round is in flight, that edit makes a NEW snapshot and a NEW round; it never mutates what the current round is judging. Full lesson: `work-items/lessons/2026-07-17-review-a-frozen-snapshot-not-a-live-tree.md`.
- **Ledger read-back before reporting a verdict (2026-07-17, live incident).** On a tracked item, a lane's verdict may be reported or acted on ONLY after the wrapper owner in `external-dispatch.md` completes its strict V2 parser, full external-nonauthorizing tuple, and untrusted/potentially-sensitive resultText handling, then the ledger is read back and confirms the terminal event for that launch `runId`. The terminal wrapper result can describe what the reviewer said, never prove that the obligation moved. This is the polling-anchor discipline applied to closure: anchor on the authoritative store, not on a self-derived signal. The incident that forced the rule: a validator defect rejected terminal events whose artifact was a repository file, the wrapper only WARNed, and TWO real `PASS` verdicts were reported to the operator from prose while the ledger held nothing (`work-items/bugs/2026-07-17-validator-artifact-workitem-relative-only.md`).
- **Close every open runId of the lane, not just the latest.** Each round's `REVISE` is its own obligation, so a lane that went `REVISE → fix → REVISE → fix → PASS` needs the final closer to carry `closesRunIds` for EVERY still-open runId of that lane. Closing only the most recent one silently leaves the earlier obligations open — the checker will say so at the gate, which is the backstop, not the plan.
- Typed dispositions only: `WAIVED:user` with the user's authorization as manual-check evidence
  (never against protected or unclassified findings); `WAIVED:security-reviewer` requires completed
  status, exact target-bound manual-check evidence, and `role` or `assignedRole` equal to
  `security-reviewer`.

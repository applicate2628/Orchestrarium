---
name: review-loop
description: "Review loop: run parallel reviews on a fix design."
---

# Review Loop

Get independent multi-angle convergence on one written fix-design artifact BEFORE the change lands. Three scope angles (two SMART verdicts + one mechanical SCOUT) review the same artifact; the loop revises and re-dispatches autonomously under an anti-drift guard and gates the human only at convergence.

This is the Codex-line binding of the provider-neutral review-loop methodology. The design trunk (`shared/references/review-loop-methodology.md`) is NOT installed; this skill carries the operative rules for the Codex runtime.

## Codex execution model (NOT the Claude background-Agent loop)

Codex's native subagent dispatch (`spawn_agent`, including the pack-pinned `worker`/`explorer` agent types) can run concurrently, but no verdict angle in this loop ever runs inside the session that authored or is revising the artifact: both verdict angles are dispatched into a fresh external process, never natively in-session (native dispatch would be exactly the internal downgrade `:70` forbids). The loop's angles are independent by **scope, not vendor** — the FOCUS each angle is given is the source of independence (see the angle table below and `:22`), so two angles on the same engine in different scopes are still distinct; vendors are symmetric, never the source. Strength-aware default assignment (below) sends the deep-reasoning scope to the most capable deep-reasoning engine via `$external-reviewer`, where ordinary `auto` resolves to Claude on the Codex line, while the same symmetry rule sends the surgical-correctness scope to the Codex-strong engine — also via `$external-reviewer`, reached through the explicit `externalProvider: codex` self-provider override (`external-dispatch.md`), since ordinary `auto` must not self-bounce into the host line's own provider. Both scopes therefore resolve to a freshly launched external process, never to the session that wrote or is revising the artifact — so the routing follows engine strength per scope, not a claim that Codex cannot dispatch concurrently or cannot supply judgment, and never a license for the artifact's author to also cast its own verdict. Whether a native `spawn_agent` run signals completion the way Claude's background `Agent()` does is unprobed here (`ASSUMPTION (UNVERIFIED)`). The loop synthesizes the angles' outputs as follows:

- The angles are dispatched as external helper runs (per `$external-brigade` and `external-dispatch.md`), each carrying its scope and the pinned objective verbatim.
- Where the host runtime cannot launch a scope concurrently, run the angles **sequentially** and synthesize their outputs; sequential execution does not change the loop's logic, only its concurrency.
- Read each angle's captured output file before counting it; a launch is not a verdict.

## The angles: two SMART verdicts + one mechanical SCOUT

Angles are defined by **SCOPE, not by vendor**. The FOCUS each is given makes it independent. Vendors are symmetric; the Codex-line default below mirrors the Claude-line mapping (the Codex host puts Claude on the large-context/strategic scope and Codex on the surgical scope, per the symmetry rule in the trunk).

| Angle | Scope | Produces | Codex-line default |
| --- | --- | --- | --- |
| **Surgical correctness** | the specific defect, contract/seam violation, "this exact line/binding is wrong", visual-bug detection | a VERDICT (PASS/REVISE) | the surgery-strong engine (Codex on its own line; the host scope) |
| **Deep reasoning** | blast-radius, cross-system ripple, large-context synthesis, ADR / framing / "is this the right shape" | a VERDICT (PASS/REVISE) | the most capable deep-reasoning engine via `$external-reviewer` (`auto` resolves to Claude on the Codex line) |
| **Mechanical scout** | fully-specified scans: "does referenced X exist?", "list every reference to Y", sketch-vs-code, symbol/style | FINDINGS (no verdict) | a fast factual role; surfaces raw findings + blind-spot hints |

The **scout does not co-judge**: it executes spelled-out mechanical scans and surfaces raw facts that FEED the two verdict angles. A scout finding is an INPUT to a verdict, not a verdict. The scout maps to a FACTUAL, non-judging role, never a judging one.

## Steps

1. **Read the routing surface.** Read and normalize `.agents/.agents-mode.yaml` first; honor `parallelMode`, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalModelMode`, and `externalCodexProfile`. Shipped `auto` stays on `codex | claude`.
2. **Confirm the runtime-verified root (hard gate).** The artifact's root must be runtime-captured THIS session. A second-hand root (commit message, prior plan, report) is runtime-verified first or the loop does not start. Never pin the root `CONFIRMED — do not re-litigate`.
3. **Write the fix-design artifact** under `.scratch/reviews/fix-design-YYYY-MM-DD-<topic>.md`: runtime-verified root with trace/`file:line` citations, candidate options with cost/risk, recommended option, implementation sketch, validation plan, and what each scope angle should evaluate.
4. **Dispatch the three scope angles** through the external surface, each with the ORIGINAL objective verbatim. Use file-based prompt delivery (write the prompt body to a temporary prompt file; argv stays for launcher flags and file paths). Run concurrently when the runtime supports it, else sequentially.
5. **Converge autonomously, persisting `review-loop-state` per round.** No human gate per round. Each round: revise the artifact to fold in every open blocker and unreconciled scout finding; run the mandatory anti-drift check (goal, admitted scope, runtime root all unchanged — drift stops the loop); re-dispatch all angles. Persist the per-round `review-loop-state` record at the force, schema, and envelope defined in `## review-loop-state ledger (structural backstop)` below — that section is the single owner of that obligation; do not restate its force or schema here. The RUNTIME enforcement is hardening invariants 7-8 (failed-lane-is-unverified, fail-closed aggregation); when DEVELOPING this pack, run `scripts/validate-review-loop-state.py` on the ledger as a dev/CI backstop.
6. **Human gate at convergence only** — never per round: (a) converged (both verdict angles PASS + all scout findings reconciled); (b) drift (present what would shift off the pinned objective); (c) deadlock (cap N=3 reached). 
7. **Implement after acceptance**, with every guard/invariant/instrumentation the angles named; run the validation plan and capture evidence before the commit gate.

## Autonomous convergence + anti-drift

- **Revise → anti-drift check → re-dispatch**, every round. Re-dispatching an unchanged artifact is forbidden (a verdict cannot change on identical input).
- **Anti-drift (mandatory):** the revised artifact must still serve the ORIGINAL pinned objective; a shift in goal, a widened scope, or a new unverified premise is drift → stop and escalate.
- **Convergence** = both VERDICT angles PASS AND every scout finding reconciled.
- **Runaway guard:** cap at **N = 3** rounds; escalate early if the same blocker survives two rounds.
- **Model-mismatch trigger:** the cap catches a blocker that stays UNCHANGED; it is blind to a blocker that MOVES — each round the fix closes one manifestation and a new adjacent one appears (a "phase-graph chase"). That recurrence signals the MODEL is wrong, not that the last fix had a bug, and a correctness loop cannot name a model mismatch. When the same defect CLASS reappears at a new spot across ~3 rounds, STOP correctness rounds and dispatch a MODEL-review lane (design/architecture angles — `$architect` / `$architecture-reviewer`, or the external-reviewer lane on the Codex line — asked "is the MECHANISM right, or is the chase a symptom of a model mismatch?" — fed the manifestation PHASE-GRAPH, not the latest diff, to name the right model or confirm the honest documented-residual floor). Resume correctness only after the model is confirmed or replaced. Per the `review-the-model-not-just-the-spec` precedent.

## Hardening invariants (every round)

1. Runtime-evidence is a hard gate, not a section (root captured this session; never pinned `CONFIRMED`).
2. Every angle answers "root proven (runtime)?", "scope unchanged?", "verification adequate?" — not only its scope.
3. Reject bare `PASS` — cite specific blockers (`file:line` / evidence) or a specific no-blocker rationale.
4. Per-round diff — what changed and why (which blocker it answers).
5. Verify OUTPUTS, not launch acknowledgements. A completion signal from a *sidecar* (watcher / notifier / background-task callback / "task done" notification) is NOT a liveness verdict on the process it watches: liveness of a launched run is proven only by a DIRECT probe of the run itself — its PID/exit status, or its own `.out`/`.err` carrying a normal-completion marker — never by a neighboring task's completion.
6. Escalate early on a stuck blocker.
7. **Failed lane is unverified.** Any expected lane that errors, dies, or hits a time/token/usage limit is UNVERIFIED. Record the failed attempt, re-dispatch that lane, and never infer a clean result from silence. Before convergence, reconcile expected lanes against substantive outputs and recorded failures; every failure must name the successful re-dispatch that supersedes it.
8. **Fail-closed aggregation.** A missing/null sub-verdict or findings payload is NOT-clean. An aggregation or gate remains `REVISE` and exits non-zero until every expected lane has substantive output and every recorded failure is reconciled.

## review-loop-state ledger (structural backstop)

A shipped loop MUST persist a per-round `review-loop-state` record under `.scratch/reviews/` so the autonomous loop leaves an auditable structural trace, and so hardening invariant 7 has a specified place to record a failed lane. Per round, persist: pinned `objective` / `scope` / `runtime_root` (identical across all rounds), `round` (≤ cap), `diff`, per verdict angle (`surgical`, `deep`) a non-empty successful `attempt_id` + a non-bare `verdict` plus the three meta-answers (`root_proven`, `scope_unchanged`, `verification_adequate`), scout `attempt_id` + `findings` + `reconciliation`, a `lane_failures` list (every expected lane that errored/died/hit a limit, each naming the failed `attempt_id`, the `failure` kind `error | died | limit`, and the successful `redispatched_as` attempt; `lane_failures: []` when none failed), and evidence references. The structural validator `scripts/validate-review-loop-state.* --self-test` (a development/CI tool in the repo, NOT shipped into the runtime) checks the SCHEMA (anchors present + unchanged, diff present, both verdict angles + scout present with non-empty unique current `attempt_id`s, no bare PASS, cap respected, `lane_failures` well-formed with each failure reconciled to its current successful re-dispatch), and treats a missing/null sub-verdict or findings payload as NOT-clean; it does not and cannot check semantics. The RUNTIME enforcement for a shipped loop is hardening invariants 7-8 above; when DEVELOPING this pack, run the validator against the current ledger as a dev/CI backstop.

**Envelope of the ledger `MUST` — what it does and does not deliver.** It binds the orchestrator in-session and is the surface a reviewer or the operator cites when the trace is missing. It is NOT mechanically enforced, and the residual is sharper than "the validator is dev-only": **no shipped mechanism observes the ledger's ABSENCE.** The schema validator's only input IS the record, and invariants 7-8 are applied in-session by the same actor that would have written it — so neither can catch the case where no record is written at all. This is measured, not feared: the failing session at `work-items/archive/2026-07/2026-07-25-review-round-cap-enforcement/design.md:1046-1049` called its fail-closed ledger helper **705 times, passed every time, then stopped calling it**, while under this same `MUST`. A stronger verb does not close that gap and a weaker one does not describe it; closing it needs a runtime-authored (T0) observer of loop-ran-without-ledger, per the authorship lattice at `design.md:1015-1018`. Tracked as decision `2026-07-26-missing-mechanism-disclosed-not-obligation-relaxed`. Until that lands, treat a missing ledger as a reviewable violation, never as a silently acceptable outcome.

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

- Every dispatched angle on a TRACKED work-item records its ledger events: launch + terminal. There
  are no shipped Codex-pack wrappers, so record them explicitly with two commands around the run:
  `python scripts/agent-run-ledger.py --work-item <item> append --event-kind launch --status running
  --gate none --role <angle-role> --lane <lane> ...` before, and the terminal (`--event-kind terminal
  --launch-run-id <id>`, gate parsed from the artifact's final `GATE:` line per the completion
  oracle) after.
- **Loop-to-PASS is the gate, not a preference:** a lane's `REVISE` closes only when THAT lane (or a
  recorded equivalent, structured fields) re-verifies `PASS` naming the exact `closesRunIds`. Author
  belief, applied fixes, or a green mechanical validator never close it; `check-work-items-state`
  FAILs on open obligations by default and the root publication gate blocks on them.
- **`HOW→VERIFY independence: VERIFY(F) owner/engine ≠ HOW(F) author`.** Independence is a property of the HOW→VERIFY edge, not the WHAT→HOW edge: a reviewer may author a fix's HOW while context is fresh; only verification of the implemented fix must stay independent. For an `inline-sufficient` finding, no separate fix-design/HOW-review pass is required before implementation, but the existing loop-to-PASS re-verification remains mandatory. **Author-exclusion for design-class (`fix-class: design-decision`) fixes:** when the implemented fix of a `design-decision` finding followed a reviewer's authored HOW, at least one discharging verdict MUST come from an angle that did not author that HOW. A distinct scope counts as distinct even on the same engine (see `## The angles`); this is stronger than the same-angle re-verification that suffices for `inline-sufficient` findings. No non-authoring verifier means no clean `PASS`: leave the HOW advisory and report the gap as `UNVERIFIED`.
- **Review a FROZEN artifact, never the live working tree (2026-07-17, live incident).** A verdict is a statement about one artifact revision, so the thing under review must not move while the round runs: dispatch at a committed revision, a `git diff` patch file, or a copied snapshot, and give the reviewer its identity (sha or digest). An angle caught this gate's engine mid-edit — including a transient syntax error — and correctly refused the patch: "the moving live target prevents accepting that patch as the current implementation". If a finding forces an edit while a round is in flight, that edit makes a NEW snapshot and a NEW round; it never mutates what the current round is judging. Full lesson: `work-items/lessons/2026-07-17-review-a-frozen-snapshot-not-a-live-tree.md`.
- **Ledger read-back before reporting a verdict (2026-07-17, live incident).** On a tracked item, a lane's verdict may be reported or acted on ONLY after reading the ledger back and confirming the terminal event exists for that launch `runId`. The reviewer's `.out` prose is evidence of what the reviewer said, never evidence that the obligation moved. This is the polling-anchor discipline applied to closure: anchor on the authoritative store, not on a self-derived signal. The incident that forced the rule: a validator defect rejected terminal events whose artifact was a repository file, the wrapper only WARNed, and TWO real `PASS` verdicts were reported to the operator from prose while the ledger held nothing (`work-items/bugs/2026-07-17-validator-artifact-workitem-relative-only.md`).
- **Close every open runId of the lane, not just the latest.** Each round's `REVISE` is its own obligation, so a lane that went `REVISE → fix → REVISE → fix → PASS` needs the final closer to carry `closesRunIds` for EVERY still-open runId of that lane. Closing only the most recent one silently leaves the earlier obligations open — the checker will say so at the gate, which is the backstop, not the plan.
- Typed dispositions only: `WAIVED:user` with the user's authorization as manual-check evidence
  (never against protected or unclassified findings); `WAIVED:security-reviewer` requires completed
  status, exact target-bound manual-check evidence, and `role` or `assignedRole` equal to
  `security-reviewer`.

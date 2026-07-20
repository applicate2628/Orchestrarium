# Review-Loop Contract

This contract is the INSTALLED Claude-line runtime binding for the autonomous parallel-review-loop. It is what `/agents-review-loop` reads at runtime and what ships with the pack, because the provider-neutral design trunk (`shared/references/review-loop-methodology.md`) is NOT installed into any runtime. The trunk owns the conceptual design; this contract carries the operative loop rules plus the concrete Claude dispatch mapping. Do not duplicate the trunk's prose into the command or the skill — they point at this contract.

## What the loop is

Get **independent multi-angle convergence** on one written fix-design artifact BEFORE the change lands. It is an autonomous, multi-round, same-artifact loop with anti-drift, gating the human only at convergence. It is NOT a single advisory opinion (`/agents-second-opinion`), NOT disjoint parallel helper lanes (`/agents-external-brigade`), and NOT a post-implementation specialist chain (`/agents-review`).

## The angles: two SMART verdicts + one mechanical SCOUT

Angles are defined by **SCOPE, not by vendor**. The FOCUS each is given is what makes it independent, so the same engine in two scopes is two distinct angles. Vendors are symmetric; the engine→scope mapping below is the Claude-line default, not a hardcode.

| Angle | Scope | Produces |
| --- | --- | --- |
| **Surgical correctness** | the specific defect, contract/seam violation, "this exact line/binding is wrong", visual-bug detection | a VERDICT (PASS/REVISE) |
| **Deep reasoning** | blast-radius, cross-system ripple, large-context synthesis, ADR / framing / "is this the right shape" / "what you are NOT doing" | a VERDICT (PASS/REVISE) |
| **Mechanical scout** | fully-specified scans: "does referenced X exist?", "list every reference to Y", sketch-vs-code, symbol/style — surfaces RAW findings + blind-spot hints | FINDINGS (no verdict) |

The **scout does not co-judge**: it executes spelled-out mechanical scans and surfaces raw facts/hints that FEED the two verdict angles and the synthesis. A scout finding is an INPUT to a verdict, not a verdict.

## Claude dispatch mapping

Each angle is dispatched DIRECTLY by the orchestrator and returns its own result — no angle re-dispatches to another provider or spawns its own waiter. Independent angles launch in parallel (`run_in_background: true`). Collection is split by lane: same-vendor Agent subagents fire a reliable notification — wait for those; an external-provider shell-out lane is verified by actively reading its captured `.out`/`.err` + process status, because that notification is not always delivered.

| Angle | `subagent_type` | Model / tier | Why this role |
| --- | --- | --- | --- |
| **Surgical verdict** | `external-reviewer` | resolved external provider (Codex, per the active `externalPriorityProfile`) | routes the surgical-correctness verdict through the external provider that sees bugs with surgical precision; provenance keeps the replaced review-side role label |
| **Deep verdict** | `architecture-reviewer` | `model: fable` | the flagship deep-reasoning tier (the `fable` flagship alias as of 2026-07, recorded from the model list — not a verified ranking) owns blast-radius / framing / "is this the right shape"; returns its strategic verdict DIRECTLY |
| **Mechanical scout** | `analyst` | `model: sonnet` | a fast factual `file:line` role for fully-specified scans; it FEEDS the verdicts and casts NO verdict |

**Anti-consolidation note (REQUIRED):** the strategic/deep angle is a direct-verdict reviewer; it is intentionally NOT `subagent_type: consultant` — consultant's external-mode shells out (the role-confusion that returns "standing by for the external provider" instead of a verdict); `consultant.md` stays untouched.

**Scout role (REQUIRED):** the mechanical scout is `analyst` (read-only, returns `file:line` facts, no verdict), never `qa-engineer`. The scout surfaces inputs; it does not gate.

## Autonomous convergence + anti-drift

The orchestrator drives the loop to convergence **without a human gate per round**; the human sees only the converged result (or an escalation). Each round, while not yet converged and on course:

1. **Revise the artifact** — fold in EVERY open blocker from the verdict angles and every unreconciled scout finding. Re-dispatching an unchanged artifact is forbidden — a verdict cannot change on identical input.
2. **Anti-drift check (mandatory, every round)** — verify the revised artifact still serves the ORIGINAL pinned objective: goal, admitted scope, and runtime-verified root all unchanged. A revision that shifts the goal, widens scope, or rests on a new unverified premise is **drift** → stop and escalate; do not re-dispatch. Anti-drift is the course-keeper that replaces the human while the loop runs.
3. **Re-dispatch** all angles on the revised artifact, carrying the ORIGINAL objective verbatim.

**Convergence** = both VERDICT angles PASS AND every scout finding is reconciled (none left dangling). Then gate the human.

**Runaway guard:** cap at **N = 3** rounds. If not converged by round 3, stop and escalate the deadlock. Escalate EARLY if the same blocker survives unchanged across two rounds.

**Model-mismatch trigger (a distinct escape the runaway cap misses).** The cap above catches a blocker that survives UNCHANGED. A different failure hides from it: the blocker MOVES — each round the fix closes one manifestation and a new adjacent one appears (a "phase-graph chase"). That recurrence is a signal that the MODEL is wrong, not that the last fix had a bug — and a correctness loop, which asks "is this fix correct?", by construction cannot name a model mismatch, so it will chase the defect around the phase graph indefinitely (a model that cannot express the invariant leaks it at a new spot every time one leak is patched). When the same defect CLASS reappears at a new spot across ~3 rounds, STOP the correctness loop and dispatch a **MODEL-review lane**: smart design angles (`architect` / `architecture-reviewer`) asked "is the MECHANISM/MODEL right, or is the chase a symptom of a model mismatch?" — fed the MANIFESTATION PHASE-GRAPH (the history of where the defect surfaced across rounds), NOT the latest diff, and asked to name the right model or confirm the current one is at its honest documented-residual floor. Return to correctness rounds only after the model is confirmed or replaced. Treat "model-mismatch suspected" (defect class recurring at a new spot for ~3 rounds) as a first-class round finding that TRIGGERS this lane, not as "found another bug, fix next round." This is the operational form of the `review-the-model-not-just-the-spec` precedent.

## Hardening invariants (every round)

Against false convergence (angles agreeing on a wrong-but-plausible result) and weak anti-drift:

1. **Runtime-evidence is a hard gate, not a section.** The artifact's runtime-verified root must be captured THIS session; a second-hand root (commit message, prior plan, report) is runtime-verified first or the loop does not start. Never pin the root as `CONFIRMED — do not re-litigate`; that silences the loop's only defense against a wrong foundation.
2. **Every angle answers** "root proven (runtime)?", "scope unchanged?", "verification adequate?" — not only its own scope.
3. **Reject bare PASS** — cite specific blockers (evidence / `file:line`) or a specific no-blocker rationale. "Looks good" is not a verdict.
4. **Per-round diff** — record what changed and why (which blocker it answers).
5. **Verify OUTPUTS, not notifications** — read the captured angle output and confirm a real verdict/findings before counting it. A completion signal from a *sidecar* (watcher / notifier / background-task callback / "task done" notification) is NOT a liveness verdict on the process it watches: liveness of a launched run is proven only by a DIRECT probe of the run itself — its PID/exit status, or its own `.out`/`.err` carrying a normal-completion marker — never by a neighboring task's completion.
6. **Escalate early on a stuck blocker.**
7. **Failed lane is unverified.** Any expected lane that errors, dies, or hits a time/token/usage limit is UNVERIFIED. Record the failed attempt, re-dispatch that lane, and never infer a clean result from silence. Before convergence, reconcile expected lanes against substantive outputs and recorded failures; every failure must name the successful re-dispatch that supersedes it.
8. **Fail-closed aggregation.** A missing/null sub-verdict or findings payload is NOT-clean. An aggregation or gate remains `REVISE` and exits non-zero until every expected lane has substantive output and every recorded failure is reconciled.

## review-loop-state ledger (structural backstop)

A SHIPPED loop in this governed pack runs autonomous-to-convergence (human only at convergence) but MUST persist a per-round `review-loop-state` record so the discipline leaves an auditable structural trace. Persist it under `.scratch/reviews/` (gitignored). Per round, the record carries:

- pinned `objective`, `scope`, `runtime_root` (MUST be identical across all rounds of one loop)
- `round` number (≤ cap)
- `diff` (what changed since the prior round and why)
- per verdict angle (`surgical`, `deep`): a non-empty successful `attempt_id` + `verdict` (PASS/REVISE, never bare — cites blockers or rationale) + answers to the three meta-questions (`root_proven`, `scope_unchanged`, `verification_adequate`)
- scout: a non-empty successful `attempt_id` + `findings` + their `reconciliation`
- `lane_failures`: every expected lane that errored/died/hit a limit, each naming the failed `attempt_id`, the `failure` kind (`error | died | limit`), and the successful `redispatched_as` attempt that supersedes it (`lane_failures: []` when none failed)
- evidence / output-artifact references

A structural validator (`scripts/validate-review-loop-state.* --self-test`, a development/CI tool kept in the repo and NOT installed into the runtime) checks the SCHEMA (anchors present + unchanged, diff present, both verdict angles + scout present with non-empty unique current `attempt_id`s, no bare PASS, cap respected, `lane_failures` well-formed with each failure reconciled to the current successful re-dispatch for that lane), treats a missing/null sub-verdict or findings payload as NOT-clean, and exits non-zero on any violation. It does NOT and cannot check the semantics (whether the reasoning was sound; that stays review territory). This is the honest boundary: structure is mechanically enforceable, soundness is not. The RUNTIME enforcement for a shipped loop is hardening invariants 7-8 above (failed-lane and fail-closed-aggregation discipline the orchestrator applies in-session); when DEVELOPING this pack, run `scripts/validate-review-loop-state.py` on the ledger as a dev/CI backstop.

### review-loop-state schema (per loop)

```yaml
objective: <one-line goal, pinned, identical across rounds>
scope: <admitted change surface, pinned, identical across rounds>
runtime_root: <runtime-captured root cause this session, pinned, identical across rounds>
rounds:
  - round: 1
    diff: <what changed since the prior round and why; for round 1, "initial artifact">
    surgical:
      attempt_id: <non-empty successful attempt id>
      verdict: REVISE            # PASS | REVISE, never bare
      blockers: [<blocker with file:line or evidence>, ...]   # or rationale on PASS
      root_proven: <yes | answer>
      scope_unchanged: <yes | answer>
      verification_adequate: <yes | answer>
    deep:
      attempt_id: <non-empty successful attempt id>
      verdict: REVISE
      blockers: [<blocker>, ...]
      root_proven: <answer>
      scope_unchanged: <answer>
      verification_adequate: <answer>
    scout:
      attempt_id: <non-empty successful attempt id>
      findings: [<raw finding>, ...]
      reconciliation: [<how each finding was addressed or folded into a verdict>, ...]
    lane_failures:              # [] when no lane failed
      - lane: <surgical | deep | scout>
        attempt_id: <failed attempt id>
        failure: <error | died | limit>
        redispatched_as: <successful attempt id for that lane, == that lane's current attempt_id>
    evidence: [<path to captured angle output / trace>, ...]
```

## When to pick the loop (one-line disambiguation)

Pick `/agents-review-loop` over the adjacent surfaces when there is real design uncertainty (2+ candidate fix options, or prior verdicts were false-positive) and you want autonomous multi-angle convergence on ONE artifact before the change lands. Use `/agents-second-opinion` for a single advisory memo, `/agents-review` for a post-implementation specialist gate, and `/agents-external-brigade` for disjoint parallel lanes that each own a different artifact.

See also `/agents-design-panel` (`agents/contracts/design-panel.md`) — the generation-side analog: it independently generates N candidate designs BEFORE a single artifact exists, converged through one mandatory synthesis, while this loop verifies ONE already-written artifact to convergence.

## Terms and Abbreviations

- **angle**: one independent review lens (surgical / deep / mechanical-scout) in the loop.
- **scout**: the mechanical angle — surfaces raw findings, casts no verdict, feeds the verdict angles.
- **anti-drift**: the per-round check that the revised artifact still serves the original pinned objective.
- **convergence**: both verdict angles PASS and all scout findings reconciled.
- **ledger / review-loop-state**: the per-round persisted record that gives the autonomous loop an auditable structural backstop.
- **ADR**: Architecture Decision Record, a written record of a significant design decision and its rationale.
- **CLI**: Command-Line Interface, a terminal command surface such as `claude` or `codex`.
- **PASS / REVISE / BLOCKED**: gate verdicts — accept, return for bounded correction, or stop on a real external blocker.

## Verdict closure (binding form of decision 2026-07-16-review-verdict-closure)

- Every dispatched angle on a TRACKED work-item records its ledger events: pass `--ledger <work-item>`
  (plus `--ledger-role/--ledger-lane/--ledger-artifact`) to `invoke-codex-prompt.sh/.ps1` /
  `invoke-claude-prompt.sh/.ps1` — the wrapper records the launch and settles the terminal via the
  shared completion oracle (final non-blank `.out` line must be exactly `GATE: PASS|REVISE`; exit 0;
  clean `.err`; else blocked).
- **Loop-to-PASS is the gate, not a preference:** a lane's `REVISE` closes only when THAT lane (or a
  recorded equivalent, structured fields) re-verifies `PASS` naming the exact `closesRunIds`. Author
  belief, applied fixes, or a green mechanical validator never close it; `check-work-items-state`
  FAILs on open obligations by default and the root publication gate blocks on them.
- **`HOW→VERIFY independence: VERIFY(F) owner/engine ≠ HOW(F) author`.** Independence is a property of the HOW→VERIFY edge, not the WHAT→HOW edge: a reviewer may author a fix's HOW while context is fresh; only verification of the implemented fix must stay independent. For an `inline-sufficient` finding, no separate fix-design/HOW-review pass is required before implementation, but the existing loop-to-PASS re-verification remains mandatory. **Author-exclusion for design-class (`fix-class: design-decision`) fixes:** when the implemented fix of a `design-decision` finding followed a reviewer's authored HOW, at least one discharging verdict MUST come from an angle that did not author that HOW. A distinct scope counts as distinct even on the same engine (see `## The angles`); this is stronger than the same-angle re-verification that suffices for `inline-sufficient` findings. No non-authoring verifier means no clean `PASS`: leave the HOW advisory and report the gap as `UNVERIFIED`.
- Typed dispositions only: `WAIVED:user` with the user's authorization as manual-check evidence
  (never against protected or unclassified findings); `WAIVED:security-reviewer` requires completed
  status, exact target-bound manual-check evidence, and `role` or `assignedRole` equal to
  `security-reviewer`.

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
| **Deep verdict** | `architecture-reviewer` | `model: opus` | the most capable deep-reasoning tier owns blast-radius / framing / "is this the right shape"; returns its strategic verdict DIRECTLY |
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

## Hardening invariants (every round)

Against false convergence (angles agreeing on a wrong-but-plausible result) and weak anti-drift:

1. **Runtime-evidence is a hard gate, not a section.** The artifact's runtime-verified root must be captured THIS session; a second-hand root (commit message, prior plan, report) is runtime-verified first or the loop does not start. Never pin the root as `CONFIRMED — do not re-litigate`; that silences the loop's only defense against a wrong foundation.
2. **Every angle answers** "root proven (runtime)?", "scope unchanged?", "verification adequate?" — not only its own scope.
3. **Reject bare PASS** — cite specific blockers (evidence / `file:line`) or a specific no-blocker rationale. "Looks good" is not a verdict.
4. **Per-round diff** — record what changed and why (which blocker it answers).
5. **Verify OUTPUTS, not notifications** — read the captured angle output and confirm a real verdict/findings before counting it.
6. **Escalate early on a stuck blocker.**

## review-loop-state ledger (structural backstop)

A SHIPPED loop in this governed pack runs autonomous-to-convergence (human only at convergence) but MUST persist a per-round `review-loop-state` record so the discipline leaves an auditable structural trace. Persist it under `.scratch/reviews/` (gitignored). Per round, the record carries:

- pinned `objective`, `scope`, `runtime_root` (MUST be identical across all rounds of one loop)
- `round` number (≤ cap)
- `diff` (what changed since the prior round and why)
- per verdict angle (`surgical`, `deep`): `verdict` (PASS/REVISE, never bare — cites blockers or rationale) + answers to the three meta-questions (`root_proven`, `scope_unchanged`, `verification_adequate`)
- scout `findings` + their `reconciliation`
- evidence / output-artifact references

A structural validator (`scripts/validate-review-loop-state.* --self-test`, a development/CI tool kept in the repo and NOT installed into the runtime) checks the SCHEMA (anchors present + unchanged, diff present, both verdict angles + scout present, no bare PASS, cap respected). It does NOT and cannot check the semantics (whether the reasoning was sound; that stays review territory). This is the honest boundary: structure is mechanically enforceable, soundness is not.

### review-loop-state schema (per loop)

```yaml
objective: <one-line goal, pinned, identical across rounds>
scope: <admitted change surface, pinned, identical across rounds>
runtime_root: <runtime-captured root cause this session, pinned, identical across rounds>
rounds:
  - round: 1
    diff: <what changed since the prior round and why; for round 1, "initial artifact">
    surgical:
      verdict: REVISE            # PASS | REVISE, never bare
      blockers: [<blocker with file:line or evidence>, ...]   # or rationale on PASS
      root_proven: <yes | answer>
      scope_unchanged: <yes | answer>
      verification_adequate: <yes | answer>
    deep:
      verdict: REVISE
      blockers: [<blocker>, ...]
      root_proven: <answer>
      scope_unchanged: <answer>
      verification_adequate: <answer>
    scout:
      findings: [<raw finding>, ...]
      reconciliation: [<how each finding was addressed or folded into a verdict>, ...]
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

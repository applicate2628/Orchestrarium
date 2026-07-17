# Review-loop methodology (provider-neutral)

Canonical DESIGN source for the autonomous parallel-review-loop. This reference is provider-neutral and is NOT installed into any runtime (per `shared/references/README.md`). Each production pack ships a thin RUNTIME binding that carries the operative rules: Claude → `agents/contracts/review-loop.md` (read by `/agents-review-loop`); Codex → `skills/review-loop/`. Keep this trunk free of pack-specific execution detail (no concrete dispatch APIs, wrapper paths, or CLI syntax); those live in the per-pack bindings.

## Purpose

Get **independent multi-angle convergence** on one written fix-design artifact BEFORE the change lands. It is distinct from the other review surfaces: not a single advisory opinion, not disjoint parallel helper lanes, not a post-implementation specialist chain — it is an autonomous, multi-round, same-artifact loop with anti-drift, gating the human only at convergence.

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
- **The most capable deep-reasoning engine** → the deep-reasoning verdict.
- **A fast/cheap engine** → the mechanical scout (reliable only for fully-specified tasks, or as a mindless broad scout that may surface a blind-spot hint; map it to a FACTUAL, non-judging role, never a judging one).
Each pack records its concrete engine→scope→role mapping in its binding.

## Autonomous convergence + anti-drift

The orchestrator drives the loop to convergence **without a human gate per round**; the human sees only the converged result (or an escalation). Each round, while not yet converged and on course:
1. **Revise the artifact** — fold in EVERY open blocker from the verdict angles and every unreconciled scout finding (re-dispatching an unchanged artifact is forbidden — a verdict cannot change on identical input).
2. **Anti-drift check (mandatory, every round)** — verify the revised artifact still serves the ORIGINAL pinned objective: goal, admitted scope, and runtime-verified root all unchanged. A revision that shifts the goal, widens scope, or rests on a new unverified premise is **drift** → stop and escalate; do not re-dispatch. Anti-drift is the course-keeper that replaces the human while the loop runs.
3. **Re-dispatch** all angles on the revised artifact, carrying the ORIGINAL objective verbatim.

**Convergence** = both VERDICT angles PASS AND every scout finding is reconciled (none left dangling). Then gate the human.

**Runaway guard:** cap at **N = 3** rounds; if not converged by round 3, stop and escalate the deadlock. Escalate EARLY if the same blocker survives unchanged across two rounds.

## Hardening invariants (every round)
Against false convergence (angles agreeing on a wrong-but-plausible result) and weak anti-drift:
1. **Runtime-evidence is a hard gate, not a section.** The artifact's runtime-verified root must be captured THIS session; a second-hand root (commit message, prior plan, report) is runtime-verified first or the loop does not start.
2. **Every angle answers** "root proven?", "scope unchanged?", "verification adequate?" — not only its scope.
3. **Reject bare PASS** — cite specific blockers (evidence/`file:line`) or a specific no-blocker rationale.
4. **Per-round diff** — record what changed and why (which blocker it answers).
5. **Verify OUTPUTS, not notifications** — read the captured angle output and confirm a real verdict/findings before counting it.
6. **Escalate early on a stuck blocker.**

## review-loop-state ledger (structural backstop)
A SHIPPED loop in a governed pack runs autonomous-to-convergence (human only at convergence) but MUST persist a per-round `review-loop-state` record so the discipline leaves an auditable structural trace (a personal/operator-owned loop may run without it — the operator accepts that risk). Per round, persist:
- pinned `objective`, `scope`, `runtime_root` (MUST be identical across all rounds of one loop)
- `round` number (≤ cap)
- `diff` (what changed since the prior round and why)
- per verdict angle: `verdict` (PASS/REVISE, never bare — cites blockers or rationale) + answers to the three meta-questions
- scout `findings` + their `reconciliation`
- evidence / output-artifact references

A structural validator checks the SCHEMA (anchors present + unchanged, diff present, both verdict angles + scout present, no bare PASS, cap respected) — it does NOT and cannot check the semantics (whether the reasoning was sound; that stays review territory). This is the honest boundary: structure is mechanically enforceable, soundness is not.

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
TRACKED work-items the relation is mechanical: the dispatch records launch+terminal events (wrapper
`--ledger`), the closer names the exact `closesRunIds`, and `check-work-items-state` fails on open
obligations. Replacement-reviewer equivalence must preserve: the review scope, independence from the
author, the same evidence target/version, and an equal-or-stronger declared tier — recorded in
structured fields, not prose. Reviews outside any work-item remain governed by the spine clause alone
(declared residual).

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
terminal event exists for that launch `runId`. The reviewer's `.out` prose is evidence of what the
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

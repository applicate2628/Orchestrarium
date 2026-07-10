# Design-panel methodology (provider-neutral)

Canonical DESIGN source for the design-panel technique — independent multi-lane GENERATION on one pinned design problem, converged by one mandatory synthesis. This reference is provider-neutral and is NOT installed into any runtime (per `shared/references/README.md`). Each production pack ships a thin RUNTIME binding that carries the operative rules: Claude → `agents/contracts/design-panel.md` (read by `/agents-design-panel`); Codex → `skills/design-panel/`. Keep this trunk free of pack-specific execution detail (no concrete dispatch APIs, wrapper paths, or CLI syntax); those live in the per-pack bindings.

## Purpose

Get independent multi-lane **generation** of candidate designs on one pinned problem BEFORE a single design exists, then converge them through one mandatory synthesis into the sole planner-eligible artifact. It is distinct from the other design and review surfaces: not a single design chain (`/agents-design`), not a review loop (which verifies one already-existing artifact), not a second opinion (a single advisory memo), and not a brigade (disjoint parallel lanes that each own a different artifact). A design-panel is a deliberate, heavier surface — N strong-model design attempts on one problem — not the default design route.

## When a panel pays (the two admitted triggers)

- **High-surface-count mechanical sweeps.** The design problem has enough independent surfaces (files, contracts, integration points) that one lane is unlikely to enumerate them completely; the union of independently-framed lanes is more complete than any single lane.
- **Open architecture choices.** The design problem has more than one defensible architecture and the choice benefits from independently explored alternatives before commitment.

Anti-triggers: a single-module additive design, or any design whose problem statement is still unverified (verify the premise first — a panel multiplies an unverified premise N times).

## The design-panel invariants (DP1–DP8)

Every installed binding carries the same stable IDs with provider-specific execution language. The IDs are conformance anchors, not a substitute for the operative text.

| ID | Required invariant |
| --- | --- |
| `DP1 — Pinned input` | The Lead accepts one objective, admitted scope, evidence/constraint package, expected final artifact, and synthesis owner before dispatch. All candidates receive the identical base package; only the declared framing overlay differs. |
| `DP2 — Quorum` | At least two valid, design-capable candidate artifacts are required. Default `N=2`; extra lanes require a distinct framing and justified merge cost. A weak, failed, empty, or duplicate-framing lane does not count. |
| `DP3 — Independence` | Independence comes from different scope/framing and sealed fresh contexts, not vendor count. Candidates do not see sibling prompts, outputs, findings, or status before returning. Different vendors with the same framing are not independent; the same capable engine in fresh contexts with genuinely different framings may be. |
| `DP4 — Candidate is input only` | Each candidate carries `Panel disposition: INPUT_ONLY`, names its lane/framing and pinned-input identity, and returns to the synthesis owner. It cannot be named the canonical `design.md`, recorded as the last accepted design, passed to `$planner`, or issue the design-stage `PASS`. |
| `DP5 — Mandatory comparison` | A predeclared synthesis owner receives **all** valid candidates and produces an explicit comparison matrix: agreement, lane-unique contributions, conflicts, omissions, and disposition with evidence/rationale. Surface-sweep panels take the verified union of compatible coverage; architecture-choice panels select or coherently combine options rather than majority-vote or blindly union incompatible designs. |
| `DP6 — Sole advance gate` | Only the synthesis artifact may carry the architect Change-Surface Contract, final numbered claims, durable decision identifiers, and `PASS` to the next stage. A panel invocation returns one public result: the synthesis or a non-success status. |
| `DP7 — Fail closed` | Missing/errored/empty lanes are `UNVERIFIED`, duplicate framings invalidate quorum, unresolved conflicts return `REVISE`, and fewer than two valid candidates return `BLOCKED:dependency`. Silence is never a clean contribution. |
| `DP8 — One shot, then verify` | Candidate generation happens once; synthesis is the convergence step. There is no round counter, re-dispatch loop, or per-round anti-drift ledger. If the synthesized design needs independent verification, hand that one artifact to review-loop or the ordinary design-review chain. |

## Artifact flow: candidate to synthesis

```text
one pinned design problem
            |
            v
   N >= 2 sealed candidate lanes (fresh contexts, distinct framings)
   each returns Panel disposition: INPUT_ONLY
            |
            v
   one mandatory synthesis (comparison + disposition matrix)
            |
            v
   the sole planner-eligible design artifact
```

A candidate is a complete, comparison-ready design proposal — it is not a sketch. It is simply not eligible to advance the design stage on its own. Only the synthesis step produces the canonical design artifact and carries the design-stage `PASS`.

## Comparison rules (SET-level, never majority-vote)

The synthesis owner compares candidates at the level of their claims and surfaces, not at the level of agreement counts — two lanes both finding "40 items" proves nothing if the sets are disjoint.

- **Surface-sweep panels** take the **verified union** of compatible coverage: every lane-unique finding is checked on its own merits and folded in, or rejected with a named reason. Matching counts are not evidence of completeness.
- **Architecture-choice panels select or coherently combine** options rather than majority-vote or blindly union incompatible designs — two incompatible architectures cannot both be adopted piecemeal.
- **Never majority-vote.** A disposition is decided by verifying each candidate's claim against evidence and accepted constraints, not by counting how many lanes proposed it.

## Relationship to review-loop

Design-panel and review-loop share one independence principle — the same engine in two distinct framings is two independent lanes; vendor count alone is not independence (see `review-loop-methodology.md#the-angles-two-smart-verdicts--one-mechanical-scout`) — applied at different stages. Design-panel is independence at **generation**: it produces N candidate designs before any single artifact exists. Review-loop is independence at **verification**: it converges multiple angles on one already-written artifact across rounds. Composition is sequential, not competing: panel generates and synthesizes once → `design.md` → optional review-loop verifies that one artifact to convergence → planner. Design-panel does not restate review-loop's angle taxonomy, round cap, or state ledger.

## Validator/review boundary

Mechanical checks (file existence, invariant-ID and marker presence, install-path presence) belong to the pack validators. Whether two framings are substantively independent rather than renamed duplicates, whether the synthesis found every unique contribution, and whether the final design is shippable all stay review territory — structure is mechanically enforceable, soundness is not.

## Terms and Abbreviations

- **candidate**: one independently-framed design lane's output; complete enough to compare but not eligible for downstream use by itself (`Panel disposition: INPUT_ONLY`).
- **framing**: the distinct scope, angle, or problem decomposition assigned to one lane; the source of independence, not the vendor.
- **fresh context**: an execution context that has not seen a sibling lane's prompt or output.
- **panel quorum**: at least two valid, design-capable, independently framed candidate artifacts (`N >= 2`).
- **synthesis**: the required comparison/merge step that produces the only planner-eligible design.
- **`INPUT_ONLY`**: candidate disposition meaning the artifact may feed synthesis but cannot advance the design stage on its own.
- **`RETURN(lead)`**: the ledger gate shape used to return a completed candidate run to the synthesis owner without declaring design-stage `PASS`.
- **review-loop**: the separate multi-round workflow that verifies one existing design to convergence.
- **PASS / REVISE / BLOCKED**: gate verdicts — accept, return for bounded correction, or stop on a real external blocker.

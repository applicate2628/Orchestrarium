# Design-Panel Contract

This contract is the INSTALLED Claude-line runtime binding for the design-panel technique. It is what `/agents-design-panel` reads at runtime and what ships with the pack, because the provider-neutral design trunk (`shared/references/design-panel-methodology.md`) is NOT installed into any runtime. The trunk owns the conceptual design; this contract carries the operative panel rules plus the concrete Claude dispatch mapping. Do not duplicate the trunk's prose into the command — it points at this contract.

## What the panel is

Get **independent multi-lane generation** of candidate designs on one pinned problem BEFORE a single design exists, then converge them through one mandatory synthesis into the sole planner-eligible artifact. It is NOT a single design chain (`/agents-design`), NOT a review loop that verifies one already-existing artifact (`/agents-review-loop`), NOT a single advisory opinion (`/agents-second-opinion`), and NOT disjoint parallel helper lanes that each own a different artifact (`/agents-external-brigade`).

## The design-panel invariants (DP1–DP8)

Every installed binding carries these stable IDs; the operative text below is what the Claude runtime follows.

| ID | Required invariant |
| --- | --- |
| `DP1 — Pinned input` | The Lead accepts one objective, admitted scope, evidence/constraint package, expected final artifact, and synthesis owner before dispatch. All candidates receive the identical base package; only the declared framing overlay differs. |
| `DP2 — Quorum` | At least two valid, design-capable candidate artifacts are required. Default `N=2`; extra lanes require a distinct framing and justified merge cost. A weak, failed, empty, or duplicate-framing lane does not count. |
| `DP3 — Independence` | Independence comes from different scope/framing and sealed fresh contexts, not vendor count. Candidates do not see sibling prompts, outputs, findings, or status before returning. Different vendors with the same framing are not independent; the same capable engine in fresh contexts with genuinely different framings may be. |
| `DP4 — Candidate is input only` | Each candidate carries `Panel disposition: INPUT_ONLY`, names its lane/framing and pinned-input identity, and returns to the synthesis owner. It cannot be named the canonical `design.md`, recorded as the last accepted design, passed to `$planner`, or issue the design-stage `PASS`. |
| `DP5 — Mandatory comparison` | The synthesis owner receives **all** valid candidates and produces an explicit comparison matrix: agreement, lane-unique contributions, conflicts, omissions, and disposition with evidence/rationale. Surface-sweep panels take the verified union of compatible coverage; architecture-choice panels select or coherently combine options rather than majority-vote or blindly union incompatible designs. |
| `DP6 — Sole advance gate` | Only the synthesis artifact may carry the architect Change-Surface Contract, final numbered claims, durable decision identifiers, and `PASS` to the next stage. A panel invocation returns one public result: the synthesis or a non-success status. |
| `DP7 — Fail closed` | Missing/errored/empty lanes are `UNVERIFIED`, duplicate framings invalidate quorum, unresolved conflicts return `REVISE`, and fewer than two valid candidates return `BLOCKED:dependency`. |
| `DP8 — One shot, then verify` | Candidate generation happens once; synthesis is the convergence step. There is no round counter, re-dispatch loop, or per-round anti-drift ledger. Hand the synthesized design to review-loop or the ordinary design-review chain if independent verification is wanted. |

## Claude dispatch mapping

| Lane | `subagent_type` | Model / tier | Why this role |
| --- | --- | --- | --- |
| Design lane (internal) | `architect` | strongest internal design tier, explicit `model:` override | the design-generation profession; the lane framing travels in the dispatch prompt (`Scope`/`Constraints` fields of the handoff template, `subagent-contracts.md`) — `architect.md` is NOT edited to carry panel-specific text |
| Design lane (external) | `$external-worker` inheriting `architect` | resolved external provider per the active `externalPriorityProfile` | worker-side generation adapter; direct provider launch, file-based prompt per `agents/contracts/external-dispatch.md`; provenance keeps the replaced-role label |
| Comparison scout (optional) | `analyst` | `model: sonnet` | factual `file:line` set-diff across candidate artifacts; FEEDS the synthesis, casts NO verdict; never `qa-engineer` |
| Synthesis | the main conversation, as Lead, inline | — | **anti-shadow-lead (REQUIRED):** synthesis is NEVER a spawned "synthesizer" subagent acting as a stand-in lead; the Lead owns the design-stage gate directly. A candidate author (an `architect`/`$external-worker` lane) may never synthesize. A pre-declared, non-candidate synthesis architect dispatch is an explicit alternative to Lead-inline, but Lead always owns the `PASS`. |

**Collection rule** (mirrors `review-loop.md`): independent lanes launch in parallel (`run_in_background: true`). Same-vendor Agent subagents return their normal result; each external-provider shell lane returns one terminal `ORCHESTRARIUM_PROVIDER_RESULT_V1` envelope. Await the wrapper process, then read its complete `resultText` and validate the primary outcome, combined status, cleanup status, process exit, timeout/cancellation flags, and gate; for tracked runs, also read back the path-free terminal ledger before counting the lane. Notifications are collection hints only; independence remains scope/framing, never vendor (per `DP3`). A died, timed-out, cleanup-failed, ledger-unsettled, or empty lane is `UNVERIFIED` — re-run it with the same framing; never silently reduce quorum.

## Skip-guards (defense in depth — both apply)

1. **Canonical-filename reservation (structural).** Candidate lanes write to reserved non-canonical names `design-<lane>.md`. ONLY the synthesis step may write `design.md`. The existing plan-stage gate already requires `design.md` before implementation or review begins, so a run that skips synthesis produces no artifact the pipeline can consume — the skip is structurally blocked, not merely a policy a reviewer must notice. Combined with the `INPUT_ONLY` candidate disposition label, this is the actual skip-prevention mechanism.
2. **Ledger convention (RECOMMENDED, AUDITABLE — not a validator-enforced gate).** When task memory is active, a candidate run should be recorded `status: completed`, `gate: RETURN(lead)` — never design-stage `PASS` — under the existing `agent-runs.jsonl`. Only the synthesis run should use `PASS`, and it must cite every candidate path as evidence. A smoke probe confirmed the source helper `scripts/validate-work-item-state.py` (installed at `.claude/agents/scripts/validate-work-item-state.py` per `scripts/install-claude.sh`) does NOT mechanically reject a candidate run marked `PASS`, nor a `RETURN(lead)` run without a cited artifact — this is an auditable convention for review to catch, not a fail-closed enforcement gate. Do not misrepresent this semantic-quality convention as a validator guarantee. No new ledger schema is introduced.

## Candidate artifact contract

Every candidate is a complete, comparison-ready design proposal that begins with these stable labels:

```text
Panel role: candidate
Panel ID: <id>
Lane ID: <id>
Framing: <one bounded, distinct framing>
Pinned input: <artifact/revision reference>
Panel disposition: INPUT_ONLY
Downstream eligibility: false
Required next gate: RETURN(lead)
```

The candidate then contains its proposed approach, alternatives, boundaries, failure modes, tests, and provisional (non-final) claims. Per DP6, the candidate does NOT carry the architect Change-Surface Contract, final numbered claims, or a durable decision-registry identifier — those are synthesis-artifact-only. Cross-cutting decisions stay candidate-local at this stage — a candidate must not create a competing durable `work-items/decisions/` record; the synthesis owner authors or updates the one canonical `status: proposed` decision record after resolving the candidates.

## Synthesis artifact contract

The synthesis owner is the Lead (inline, default) or a pre-declared, non-candidate synthesis architect dispatch. The synthesis artifact must contain:

1. the pinned input and a one-line scope-conformance check;
2. the panel roster: lane, framing, resolved execution path/model, candidate path;
3. an independence check (fresh context, no sibling-output exposure);
4. the comparison/disposition matrix (columns: claim/surface, lane source, agreement-or-unique, conflict, evidence checked, final disposition + rationale);
5. unresolved conflicts, or a specific "none" rationale;
6. one coherent final design package, including the architect Change-Surface Contract;
7. final numbered `{ guarantee, single-owner, enforcement-probe }` claims;
8. canonical proposed decision-registry IDs for any cross-cutting/long-lived decision;
9. final `PASS | REVISE | BLOCKED:<class>`.

`PASS` is valid only when the run is `completed`, points to the synthesis artifact (`design.md`), and cites one evidence entry per candidate plus the comparison artifact itself.

## Public return contract

The command does not stop after candidate collection. It returns exactly one of:

- the completed synthesized design and its gate;
- `REVISE` with the comparison conflict that prevents a coherent design;
- `BLOCKED:dependency` when quorum or a synthesis owner is unavailable;
- `BLOCKED:prerequisite` when the accepted brief/research input is missing or stale.

It never returns one candidate as "the design." There is no documented success return path between fan-out and synthesis.

## When to pick the panel (one-line disambiguation)

Pick `/agents-design-panel` when the design problem is a high-surface-count sweep or an open architecture choice and you want independently-framed candidate generation BEFORE a design exists. Pick `/agents-design` for an ordinary single-architect design chain. Pick `/agents-review-loop` to converge multiple angles on ONE already-written artifact — design-panel generates candidates; review-loop verifies one existing artifact. See also `/agents-review-loop` (the verification-side analog).

## Terms and Abbreviations

- **candidate**: one independently-framed lane's design output; complete enough to compare but not eligible for downstream use by itself (`Panel disposition: INPUT_ONLY`).
- **framing**: the distinct scope, angle, or problem decomposition assigned to one lane; the source of independence, not the vendor.
- **fresh context**: an execution context that has not seen a sibling lane's prompt or output.
- **panel quorum**: at least two valid, design-capable, independently framed candidate artifacts (`N >= 2`).
- **synthesis**: the required comparison/merge step that produces the only planner-eligible design.
- **`INPUT_ONLY`**: candidate disposition meaning the artifact may feed synthesis but cannot advance the design stage on its own.
- **`RETURN(lead)`**: the ledger gate shape used to return a completed candidate run to the synthesis owner without declaring design-stage `PASS`.
- **anti-shadow-lead**: the rule that synthesis is performed by the Lead inline (or a pre-declared non-candidate architect), never by a spawned subagent acting as a stand-in orchestrator.
- **PASS / REVISE / BLOCKED**: gate verdicts — accept, return for bounded correction, or stop on a real external blocker.

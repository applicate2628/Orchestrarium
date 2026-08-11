---
name: design-panel
description: "Compare independent candidate designs, synthesize one."
---

# Design Panel

Get independent multi-lane generation of candidate designs on one pinned problem BEFORE a single design exists, then converge them through one mandatory synthesis into the sole planner-eligible artifact.

This is the Codex-line binding of the provider-neutral design-panel methodology. The design trunk (`shared/references/design-panel-methodology.md`) is NOT installed; this skill carries the operative rules for the Codex runtime.

## Codex execution model (sealed external candidate lanes)

`DP3-NATIVE-ROUTE-UNVERIFIED`: native subagent sealing depends on runtime configuration this skill does not inspect, so it is not an eligible candidate route. Every candidate uses the existing direct `$external-worker` boundary with file-based prompt delivery. An absent CLI, died lane, or empty output is caught visibly by `DP7` as `UNVERIFIED` or `BLOCKED:dependency`; no internal fallback may replace an unavailable external candidate.

Candidate launch arguments MUST NOT select or resume an existing provider session: Claude `--continue`/`-c`, `--resume`/`-r`, `--session-id`, `--fork-session`, `--from-pr`, and `--teleport`, plus the Codex `exec resume` route, are forbidden. Inspect the resolved provider argv before launch; a session-reuse route makes that candidate `UNVERIFIED` and it is never counted toward quorum.

- Each candidate lane is dispatched as a design-capable worker run (per `$external-worker` and `external-dispatch.md`), carrying the identical pinned input; only the framing overlay differs.
- Where the host runtime cannot launch a lane concurrently, run the lanes **sequentially** in fresh external contexts and synthesize their outputs afterward; sequential execution does not change the panel's logic, only its concurrency — each lane still needs a fresh context that has not seen a sibling lane's output.
- Read each lane's captured output file before counting it; a launch is not a candidate.

## The design-panel invariants (DP1–DP8)

| ID | Required invariant |
| --- | --- |
| `DP1 — Pinned input` | One objective, admitted scope, evidence/constraint package, expected final artifact, and synthesis owner are fixed before dispatch. All candidates receive the identical base package; only the framing overlay differs. |
| `DP2 — Quorum` | At least two valid, design-capable candidates are required. Default `N=2`; a weak, failed, empty, or duplicate-framing lane does not count. |
| `DP3 — Independence` | Independence comes from different scope/framing and sealed fresh contexts, not vendor count. No lane sees a sibling's prompt, output, or status before returning. Different vendors with the same framing are not independent; the same capable engine in fresh contexts with genuinely different framings may be. |
| `DP4 — Candidate is input only` | Each candidate carries `Panel disposition: INPUT_ONLY`, names its lane/framing and pinned-input identity, and returns to the synthesis owner. It cannot become the canonical `design.md`, be recorded as the last accepted design, be passed to the planner, or issue the design-stage `PASS`. |
| `DP5 — Mandatory comparison` | The synthesis owner receives ALL valid candidates and produces an explicit comparison matrix. Surface-sweep panels take the verified union of compatible coverage; architecture-choice panels select or coherently combine options — never majority-vote or blind union of incompatible designs. |
| `DP6 — Sole advance gate` | Only the synthesis artifact carries the Change-Surface Contract, final numbered `{guarantee, single-owner, enforcement-probe}` claims, and durable decision-registry identifiers, plus `PASS`. Candidate artifacts carry none of these. A panel invocation returns one public result: the synthesis or a non-success status. |
| `DP7 — Fail closed` | Missing/errored/empty lanes are `UNVERIFIED`; duplicate framings invalidate quorum; unresolved conflicts return `REVISE`; fewer than two valid candidates return `BLOCKED:dependency`. |
| `DP8 — One shot, then verify` | Candidate generation happens once; synthesis is the convergence step. No round counter or anti-drift ledger. Hand the synthesized design to `$review-loop` if independent verification is wanted. |

## Steps

1. **Read the routing surface.** Read and normalize `.agents/.agents-mode.yaml` first; honor `parallelMode`, `externalProvider`, `externalPriorityProfile`, and the other structured routing keys. Shipped `auto` stays on `codex | claude`.
2. **Pinned-input gate.** Confirm one admitted objective, scope, and evidence/constraint package exist. A panel multiplies an unverified premise across every lane — verify it first.
3. **Choose N and framings.** Default `N=2`. Pick a distinct, bounded framing per lane and pre-register them (lane id, framing, resolved role) before dispatch.
4. **Dispatch the candidate lanes** through the external surface, each carrying the identical pinned input and its own framing, with file-based prompt delivery (write the prompt body to a temporary file; argv stays for launcher flags and file paths). Inspect the resolved provider argv and fail closed on every session-reuse route listed by `DP3-NATIVE-ROUTE-UNVERIFIED`. Run concurrently when the runtime supports it, else sequentially in fresh contexts. Each lane writes its candidate to `design-<lane>.md`, never `design.md`.
5. **Collect.** Read each lane's captured output before counting it. A died, timed-out, or empty lane is `UNVERIFIED` — re-run it with the same framing; never silently reduce quorum below `N=2`.
6. **Synthesize.** The orchestrating session performs the synthesis directly (never a spawned "synthesizer" run acting as a stand-in lead, and never a candidate author). Produce the comparison/disposition matrix and write the sole canonical `design.md`, citing every candidate as evidence.
7. **Return exactly one public result:** the synthesized design and its gate (`PASS | REVISE | BLOCKED:dependency | BLOCKED:prerequisite`). Never present one candidate as "the design." Candidate artifacts stay as work-item inputs and are never handed to the planner.

## Skip-guards (defense in depth — both apply)

1. **Canonical-filename reservation** — candidate lanes write `design-<lane>.md`; only synthesis writes `design.md`. The existing plan-stage gate already requires `design.md`, so a skipped synthesis leaves no artifact the pipeline can consume. This is the STRUCTURAL skip-prevention mechanism.
2. **Ledger convention (RECOMMENDED, AUDITABLE — not a validator-enforced gate)** — when task memory is active, a candidate run is recorded in the work-item's `agent-runs.jsonl` as `status: completed`, `gate: RETURN(lead)` — never design-stage `PASS`; only the synthesis run should use `PASS`, citing every candidate as evidence. A smoke probe confirmed the source helper `scripts/validate-work-item-state.py` (installed at `.agents/skills/lead/scripts/validate-work-item-state.py` for repo-local installs, `~/.codex/skills/lead/scripts/validate-work-item-state.py` for global installs) does NOT mechanically reject a candidate run marked `PASS`, nor a `RETURN(lead)` run missing a cited artifact — this convention is an auditable review trail, not a fail-closed gate. The actual structural skip-prevention is skip-guard #1 above plus the `INPUT_ONLY` candidate label. No new ledger schema is introduced.

## Synthesis artifact contract

The synthesis owner is the orchestrating session, performing synthesis directly (never a spawned "synthesizer" run, never a candidate author). The synthesis artifact (`design.md`) must contain:

1. the pinned input and a one-line scope-conformance check;
2. the panel roster: lane, framing, resolved execution path/model, candidate path;
3. an independence check (fresh context, no sibling-output exposure);
4. the SET-level comparison/disposition matrix (columns: claim/surface, lane source, agreement-or-unique, conflict, evidence checked, final disposition + rationale);
5. unresolved conflicts, or a specific "none" rationale;
6. one coherent final design package, including the Change-Surface Contract;
7. final numbered `{guarantee, single-owner, enforcement-probe}` claims;
8. canonical proposed decision-registry IDs for any cross-cutting/long-lived decision;
9. final `PASS | REVISE | BLOCKED:<class>`.

`PASS` is valid only when the run is `completed`, points to the synthesis artifact (`design.md`), and cites one evidence entry per candidate plus the comparison itself. Candidate artifacts carry none of items 6-8 (DP6).

## Rules

- This is a utility skill, not a new specialist role, and not a replacement for `$lead`.
- Only the synthesis step may write `design.md`; candidate lanes never see each other's output.
- Do not silently downgrade an external lane to internal execution.
- Do NOT commit, push, or install from this skill. Implementation stops at the human commit gate.

## Non-goals

- Not an ordinary single-architect design chain (that is `$design`).
- Not a review loop that verifies one already-existing artifact (that is `$review-loop`).
- Not a single advisory opinion (that is `$second-opinion` / `$consultant`).
- Not disjoint parallel helper lanes that each own a different artifact (that is `$external-brigade`).
- Not for a single-module additive design, and not for a problem statement that is still unverified.

## Terms and Abbreviations

- **candidate**: one independently-framed lane's design output; complete enough to compare but not eligible for downstream use by itself (`Panel disposition: INPUT_ONLY`).
- **framing**: the distinct scope, angle, or problem decomposition assigned to one lane; the source of independence, not the vendor.
- **fresh context**: an execution context that has not seen a sibling lane's prompt or output.
- **synthesis**: the required comparison/merge step that produces the only planner-eligible design.
- **`RETURN(lead)`**: the ledger gate shape used to return a completed candidate run without declaring design-stage `PASS`.
- **PASS / REVISE / BLOCKED**: gate verdicts — accept, return for bounded correction, or stop on a real external blocker.

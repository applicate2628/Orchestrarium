# Bug: the REVISE cap value `3` is re-typed at nine sites with no single owner

- id: 2026-07-25-cap-three-no-single-owner
- context: 2026-08-11-separate-revise-cap-contracts
- status: fixed
- severity: low
- area: cross-pack governance constants
- found-by: `$architect` (2026-07-25-review-round-cap-enforcement design)

## Description

The cap of 3 iterations before a REVISE loop must escalate to the operator is stated independently
at nine live sites across both packs, the shared spine, the shared reference trunk, its Russian
mirror, and one validator default. Each is a separate hand-typed assertion of the same
cross-cutting invariant.

| Site | Mechanism |
| --- | --- |
| `shared/AGENTS.shared.md:40` | spine — "escalate after 3 consecutive cycles for the same role and artifact" |
| `src.claude/skills/lead/SKILL.md:243` | lead REVISE cap |
| `src.claude/agents/contracts/operating-model.md:219-221` | REVISE iteration cap |
| `src.codex/skills/lead/operating-model.md:385-387` | REVISE iteration cap (Codex mirror) |
| `src.claude/agents/contracts/review-loop.md:45` | review-loop runaway guard `N = 3` |
| `src.codex/skills/review-loop/SKILL.md:47` | review-loop runaway guard `N = 3` |
| `shared/references/review-loop-methodology.md:37` | trunk runaway guard |
| `shared/references/ru/review-loop-methodology.md:37` | Russian mirror |
| `scripts/validate-review-loop-state.py:45` | `DEFAULT_CAP = 3` |

Adjacent restatements also exist at `src.claude/commands/agents-security.md:31`,
`src.claude/commands/agents-perf.md:44`, and `cross-pack-reconciliation.md:26`.

Note that two DIFFERENT mechanisms share the value: the lead's REVISE-iteration cap (same role, same
artifact) and the review-loop technique's round cap. They are governed together by coincidence of
value, not by a shared owner.

## Why it matters

Architecture law C1 — one owner per cross-cutting invariant — is violated: a mode predicate, shared
constant, or flag meaning should have exactly one owner all consumers call, and re-typing it "to
stay consistent" is the bug. The practical consequence is that retuning the cap (a question that
came up directly during the review-round-cap-enforcement design) requires a coordinated nine-site
edit across two packs plus a Russian mirror, with no mechanical guard against a partial application.

There is precedent machinery for exactly this class: `cross-pack-reconciliation.md` maps shared
semantic blocks, and `validate-skill-pack.sh` already pins cross-pack reference parity by normalized
SHA-256. Neither currently covers the cap value.

## Expected

Either one owner all surfaces cite, or — where prose duplication is unavoidable across a hard pack
boundary — a drift gate that fails when the nine sites disagree (the "generated-from-one-source or
drift-gated duplicate" exception in the layering laws).

## Scope note

NOT folded into the `2026-07-25-review-round-cap-enforcement` design. That design deliberately
leaves all nine sites byte-unchanged and adds a separate structural tier instead of retuning the
number — the nine-site blast radius is precisely why. Consolidating them is its own change surface;
scope expansion is the orchestrator's decision.

## MEASURED 2026-07-26 — sharper than "no single owner": the number is THREE different rules

Swept across `shared/`, `src.claude/`, `src.codex/`, `scripts/` by `$lead`. The constant `3` is declared
in at least **six** places, and they do not express one rule wearing six copies — they express **three
different rules wearing the same number**:

| Scope actually bounded | Declared at |
| --- | --- |
| **rounds of a review loop** | `shared/references/review-loop-methodology.md:37`, `src.claude/agents/contracts/review-loop.md:45` |
| **consecutive `REVISE` cycles for one role AND one artifact** | `shared/references/subagent-operating-model.md:176`, `shared/AGENTS.shared.md:40`, `shared/references/workflow-strategy-comparison.md:32` |
| **iterations per stage** | `src.claude/agents/contracts/operating-model.md:221` |

A loop round, a per-role-per-artifact `REVISE` cycle, and a per-stage iteration are **three distinct
quantities**. An actor can satisfy one while violating another, and no text reconciles them.

**Why this is not pedantry — it is the reason the cap is unenforceable.** The runaway review loop
recorded in `2026-07-26-review-loop-termination-vocabulary` ran **8 rounds** across two tracks. Ask which
rule that broke:

- the loop-round cap — yes, if "round" means a full two-track cycle;
- the per-role-per-artifact `REVISE` cap — **not obviously**: two tracks alternated, and `qa` returned
  `PASS` at r7, so no single role/artifact accumulated three consecutive `REVISE`s in an unbroken run;
- the per-stage iteration cap — undefined, because "stage" is not the unit a review loop iterates.

So the loop plausibly violated **one** reading and complied with another, and nothing in the pack
adjudicates. A cap that cannot be evaluated against a concrete trace cannot be mechanized, which is
exactly the finding recorded independently in that design (`§1.1`: the cap exists, is prose, and prose is
**measured** non-binding — twice).

**Implication for the fix.** Assigning a single owner is necessary but not sufficient. The owner must
first decide **which quantity `N = 3` bounds**, then either state the other two as separate named
constants with their own values, or delete them. Copying one number into one file while the three scopes
stay conflated reproduces the defect with better provenance.

Terminal-at: 2026-08-11T20:08:17Z
Resolution: The shared spine now solely owns the generic same-role/same-artifact correction-cycle number, while review_loop_state.py::REVIEW_LOOP_ROUND_CAP separately owns autonomous review rounds; every allowed hard-boundary duplicate is drift-gated.
Evidence: implementation.md, qa.md, and architecture-review.md are PASS; dedicated RED-to-GREEN contract, full review-loop/dispatch suites, both pack validators, spine, CodeGraph, staged-boundary, and diff checks are green.

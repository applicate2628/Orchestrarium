# Task

Surface: `R10 $algorithm-scientist`
Artifact type: `invariant and proof memo`
Modality family: `formal reasoning`

## Goal

Produce `candidate/algorithm-invariant-proof-memo.md` for the benchmark runner's deterministic
minimal rerun planner.

The memo must be suitable input to later implementation and later review. It must stay in the
algorithm-scientist lane: formalize the problem, choose and compare algorithm families, state
invariants, justify correctness, and explain edge cases before code exists. Do not return a code
patch, a governance packet, or a findings-only review.

## Required output content

Your memo must include:

1. a formal problem statement
2. assumptions and limits
3. a recommended approach
4. alternative approaches and tradeoffs
5. explicit invariants
6. a correctness sketch
7. complexity analysis
8. failure modes and edge cases
9. edge-case test recommendations
10. a numbered claims section
11. a final gate decision of `PASS`, `REVISE`, or `BLOCKED`

## Evidence use rule

Reference the supplied evidence IDs (`E1` through `E5`) in the memo. The scenario is scored on how
well the formulation traces back to the evidence instead of drifting into generic algorithm prose.

## Scope discipline

- Edit only `candidate/algorithm-invariant-proof-memo.md`
- Treat the task as exact formalization work, not approximate heuristic advice
- Distinguish proved guarantees from assumptions and from operational preferences
- Keep the answer non-web and memo-only
- Do not assume implementation details that are not justified by the evidence

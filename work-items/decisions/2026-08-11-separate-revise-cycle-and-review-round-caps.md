- id: 2026-08-11-separate-revise-cycle-and-review-round-caps
- status: accepted
- decided-by: $architecture-reviewer
- date: 2026-08-11
- context: cross-cutting governance limits
- supersedes: none
- superseded-by: none

# Decision: separate Lead correction cycles from autonomous review-loop rounds

## Decision

Treat the generic Lead cap and the autonomous review-loop cap as independent policies even while both default to 3.

- The shared spine owns the only numeric declaration for consecutive `REVISE` cycles on the same role and artifact. Other generic surfaces cite that policy without retyping the number.
- `scripts/review_loop_state.py::REVIEW_LOOP_ROUND_CAP` owns the autonomous loop's numeric round default. Self-contained provider review-loop bindings may duplicate `N = 3 rounds` only under a drift gate tied to that runtime owner.
- Delete the unsupported `per stage` interpretation and any reconciliation prose that claims identical semantics without naming the unit.

## Consequences

Changing one cap no longer silently changes or appears to change the other. Generic Lead adherence remains instruction-enforced; autonomous review-loop round count remains runtime-enforced.

## Terms and Abbreviations

- **Cycle:** one completed correction/re-evaluation result for the same role and artifact.
- **Round:** one full autonomous multi-angle review iteration.

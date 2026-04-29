# S10 Algorithm Invariant Proof Memo

`S10` benchmarks `R10 $algorithm-scientist` on a non-web, evidence-heavy formal reasoning task.
The candidate is asked to produce one invariant and proof memo for a deterministic minimal rerun
planner over a dependency graph used by the local benchmark runner. The bundle stays entirely in
the scientist lane: formalize the problem, name the invariants, compare viable approaches, sketch
correctness, and bound the complexity before any implementation work begins.

## Scenario summary

The runner currently recomputes a rerun plan after accepted artifacts change. The existing
heuristic has four known failures:

1. nodes can be re-enqueued twice when multiple changed predecessors converge
2. tie-breaking leaks filesystem or map iteration order
3. an irrelevant cycle elsewhere in the graph can block a clean affected region
4. empty change sets and self-loops are not handled explicitly

The immutable inputs define the graph semantics, the exact affected-set contract, observed failure
traces, scale expectations, and several plausible algorithm families. A passing answer must turn
that material into a precise algorithm note, not a code patch and not generic architecture prose.

All materials in this bundle are synthetic and local to the repository.

## Expected candidate work

Edit only `candidate/algorithm-invariant-proof-memo.md`.

Use the evidence packet in `inputs/` to produce an algorithm-scientist artifact with:

- a formal problem statement
- explicit assumptions and limits
- a recommended approach
- viable alternatives with tradeoffs
- explicit invariants
- a correctness sketch
- complexity analysis
- failure-mode and edge-case reasoning
- edge-case test recommendations
- numbered claims and a final gate decision

## What this bundle tests

- precision in turning an operational note into a formal algorithmic problem
- invariant-driven reasoning instead of intuition or design prose
- complexity tradeoffs tied to actual workload evidence
- role fidelity for `R10 $algorithm-scientist`

## Bundle map

- `inputs/` holds the immutable evidence packet
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected formulation, invariants, and scoring anchors
- `verifiers/` checks bundle shape and the completed proof memo

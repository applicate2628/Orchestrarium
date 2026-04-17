# Oracle

The oracle material defines the ground-truth algorithmic shape for `S10`.

## Expected read

The correct memo stays in the algorithm-scientist lane and anchors the analysis in the supplied
evidence. A strong answer formalizes rerun planning over the affected subgraph, recommends a stable
Kahn-style pass with explicit cycle-witness handling on failure, names the required invariants,
compares viable alternatives, and ties complexity tradeoffs and edge cases back to the evidence.
The final gate decision should be `PASS` because the formulation is precise enough to implement and
prove against without adding new product or policy decisions.

## Included oracle files

- `algorithm-invariant-proof-contract.json` provides machine-readable verifier anchors
- `expected-formulation.md` describes the formal problem and recommended approach
- `invariant-set.md` lists the expected invariants and why they matter
- `alternative-tradeoffs.md` explains the viable alternatives and why one is preferred
- `prohibited-patterns.md` lists role drift and proof-avoidance failures
- `scoring-anchors.md` translates the scoring model into `S10`-specific pass and fail signals

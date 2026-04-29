# Scoring Anchors

These anchors apply the `scientist, constraints` profile to `S10`.

## Strong pass signals

- the memo defines `D1` through `D4` and uses `E1` through `E5`
- `A1` through `A3` compare viable approaches instead of strawmen
- `I1` through `I5` are explicit and actually support the correctness sketch
- the recommended algorithm is an affected-subgraph stable Kahn pass with a failure-path cycle
  witness
- complexity claims are tied to `|V_a|` and `|E_a|` or an equivalent affected-subgraph notation
- `X1` through `X5` and `T1` through `T5` cover the observed and implied edge cases
- the final gate decision is `PASS`

## Common failure signals

- the memo says "topological sort" without defining the exact input, output, or affected-set
  semantics
- alternatives are dismissed informally without concrete tradeoffs
- the correctness sketch does not explain duplicate prevention or deterministic tie-breaking
- global cycles are treated as blockers even when the affected region is acyclic
- the answer drifts into implementation patching or generic process advice

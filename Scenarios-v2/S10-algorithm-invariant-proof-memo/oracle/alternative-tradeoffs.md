# Alternative Tradeoffs

The memo should compare at least three viable algorithm families before committing.

## Expected comparison anchors

- `A1`: full-graph stable Kahn pass
  - simplest proof surface
  - extra work on unaffected components
  - can block on irrelevant cycles unless extra filtering is added

- `A2`: affected-subgraph DFS postorder
  - linear and compact
  - stable output and witness extraction are harder to justify cleanly

- `A3`: affected-subgraph stable Kahn pass with failure-path witness extraction
  - best fit for the exact affected-set contract
  - straightforward uniqueness and determinism invariants
  - needs an explicit witness step on failure

An answer may mention SCC condensation as a fourth option, but the preferred recommendation is the
affected-subgraph stable Kahn approach because it matches `E2`, explains `E3`, and satisfies `E4`
without unnecessary machinery.

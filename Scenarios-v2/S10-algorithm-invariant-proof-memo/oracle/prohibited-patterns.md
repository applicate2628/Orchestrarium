# Prohibited Patterns

These failures should score poorly even if the memo sounds polished.

- generic design prose with no formal definitions, invariants, or proof obligations
- implementation-heavy pseudocode or code patch guidance that replaces the memo
- treating deterministic ordering as a cosmetic preference rather than part of the contract
- claiming that any cycle in the global graph must block the run, even when it is outside the
  affected subgraph
- asymptotic claims with undefined variables or no tie back to `E4`
- approximate, probabilistic, or policy-style rerun logic when `E2` requires exact affected-set
  semantics
- drifting into computational-scientist modeling, security constraints, or performance-policy
  writing instead of algorithm formalization

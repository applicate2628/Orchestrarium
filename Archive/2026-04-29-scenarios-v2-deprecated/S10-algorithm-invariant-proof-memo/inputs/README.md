# Inputs

This directory is the immutable evidence packet for `S10`.

## Included materials

- `task.md` defines the benchmark task and the required output contract
- `system-goal-and-graph.md` gives the formal graph goal and example graph (`E1`)
- `algorithm-contract.md` defines the exact rerun-planner guarantees (`E2`)
- `failure-traces.md` records the observed heuristic failures that the memo must explain (`E3`)
- `scale-and-complexity-notes.md` defines the relevant size and complexity constraints (`E4`)
- `candidate-approach-notes.md` lists the viable algorithm families and tradeoff hints (`E5`)

The evidence is intentionally dense. A generic "use a topological sort" answer will miss the exact
affected-set contract, the deterministic ordering rule, and the failure-path obligations this
scenario expects.

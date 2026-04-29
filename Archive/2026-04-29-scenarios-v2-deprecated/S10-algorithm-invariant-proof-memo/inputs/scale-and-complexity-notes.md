# E4 Scale and Complexity Notes

The implementation team expects the following operating envelope:

- up to `50,000` nodes
- up to `200,000` directed edges
- typical changed-set size between `1` and `80` nodes
- common-case affected region under `5%` of the full graph
- occasional worst-case full-wave reruns where the affected region approaches the whole graph

## Complexity expectations

- linear or near-linear work in the affected region is preferred
- an extra `log n` factor for deterministic priority handling is acceptable
- repeated full-graph rescans per emitted node are not acceptable
- memory proportional to the affected region is preferred; full-graph auxiliary state is tolerated
  only if it materially simplifies correctness

## Priority rule

Correctness and deterministic replay are more important than shaving a logarithmic factor. A clean
proof with `O((|V_a| + |E_a|) log |V_a|)` behavior is acceptable if it preserves exactness and
stable order, where `V_a` and `E_a` are the affected-subgraph vertices and edges.

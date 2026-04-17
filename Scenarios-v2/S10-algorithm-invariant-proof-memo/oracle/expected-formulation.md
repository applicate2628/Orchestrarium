# Expected Formulation

The memo should formalize the rerun-planner task as an exact graph problem, not a heuristic policy
discussion.

## Expected definitions

- `D1`: define the directed graph `G = (V, E)`, the changed set `C`, and the stable key
  `k(node) = (phase_rank, pack_id, surface_id, node_id)` from `E1`
- `D2`: define the affected set `A` as the exact forward reachability closure of `C`
- `D3`: define the output as either a stable topological order of the affected subgraph or a cycle
  witness drawn only from that affected subgraph
- `D4`: state the objective explicitly: exact rerun coverage, deterministic order, and fail-closed
  detection of impossible affected regions

## Expected recommended approach

The preferred answer is a hybrid of:

1. forward reachability from `C` to compute the affected set
2. affected-subgraph indegree counting only within `A`
3. a stable Kahn-style ready queue ordered by the declared stable key
4. a failure-path witness extraction step over the leftover affected nodes if the emitted-node count
   is smaller than `|A|`

Important implications:

- the empty changed set returns an empty order immediately
- unaffected nodes are not scanned repeatedly once `A` has been isolated
- a cycle outside `A` is irrelevant
- a self-loop inside `A` is an immediate failure case that must surface in the witness

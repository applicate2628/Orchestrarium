# E1 System Goal and Graph Model

The benchmark runner stores accepted artifacts in a dependency graph. Each node is a rerunnable
unit such as a planning document, scenario bundle, or review packet. A directed edge `u -> v`
means `v` depends on `u`, so `v` must be reconsidered if `u` changes.

## Required output behavior

Given:

- a directed graph `G = (V, E)`
- a finite set of changed nodes `C`
- a stable ordering key `k(node) = (phase_rank, pack_id, surface_id, node_id)`

the rerun planner must return exactly one of:

1. an ordered rerun list containing exactly the changed nodes and every node reachable from them, or
2. a cycle witness drawn only from the affected region when no valid rerun order exists there

Additional rules:

- if `C` is empty, the rerun list is empty
- a cycle outside the affected region must not block a valid affected region
- ties between simultaneously ready nodes must be resolved by the stable key, never by filesystem
  order, hash-map order, wall clock, or randomization

## Stable key details

`phase_rank` is a fixed integer used only to stabilize the output:

- `1` for planning artifacts
- `2` for scenario bundles
- `3` for review and verifier artifacts

`pack_id`, `surface_id`, and `node_id` are compared lexicographically after `phase_rank`.

## Example graph

Nodes:

- `N1` planning-backlog (`phase_rank=1`, `pack_id=P00`, `surface_id=R00`)
- `N2` pack-specs (`phase_rank=1`, `pack_id=P00`, `surface_id=R00`)
- `N3` scoring-model (`phase_rank=1`, `pack_id=P00`, `surface_id=R00`)
- `N4` phase-plan (`phase_rank=1`, `pack_id=P00`, `surface_id=R00`)
- `N5` S10 bundle (`phase_rank=2`, `pack_id=P03`, `surface_id=R10`)
- `N6` S25 QA bundle (`phase_rank=3`, `pack_id=P06`, `surface_id=R25`)
- `N7` archive-index (`phase_rank=3`, `pack_id=P00`, `surface_id=R00`)

Edges:

- `N1 -> N4`
- `N2 -> N4`
- `N3 -> N4`
- `N2 -> N5`
- `N4 -> N5`
- `N5 -> N6`

Changed set:

- `C = {N2}`

Expected affected set:

- `{N2, N4, N5, N6}`

One valid stable order:

1. `N2`
2. `N4`
3. `N5`
4. `N6`

`N1`, `N3`, and `N7` are not rerun because they are not reachable from `N2`.

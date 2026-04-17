# E2 Algorithm Contract

This file defines the exact semantic contract for the rerun planner.

## Definitions

- `affected`: a node is affected iff it is in `C` or is reachable from some node in `C`
- `affected subgraph`: the induced subgraph on the affected nodes only
- `ready`: an affected node is ready iff every affected predecessor has already been emitted
- `emitted`: a node that has been appended to the rerun output exactly once
- `cycle witness`: a non-empty set or ordered walk drawn only from the remaining affected nodes that
  proves why no valid rerun order exists

## Required guarantees

1. exactness: the planner must output every affected node and no unaffected node
2. uniqueness: duplicate edges or multiple changed ancestors may not duplicate a node in the output
3. determinism: identical inputs must produce identical rerun output across machines
4. locality: failures outside the affected subgraph may not poison an otherwise valid rerun plan
5. fail-closed behavior: a self-loop, missing affected predecessor, or directed cycle inside the
   affected subgraph must yield a cycle witness instead of a partial success result

## Non-goals

- minimizing wall-clock time by changing the semantics of the exact affected set
- approximate or probabilistic rerun selection
- parallel execution planning after the rerun order has been computed

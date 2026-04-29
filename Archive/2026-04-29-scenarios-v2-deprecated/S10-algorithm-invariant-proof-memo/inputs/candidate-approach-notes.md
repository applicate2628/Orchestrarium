# E5 Candidate Approach Notes

These are the viable families that the memo should compare before choosing one.

## Approach family A: full-graph stable Kahn pass

Run a stable topological pass over the entire graph after marking changed nodes.

Pros:

- simple to explain
- one familiar correctness story

Cons:

- does unnecessary work on unaffected components
- can be blocked by cycles that are irrelevant to the current rerun request unless special casing is
  added later

## Approach family B: affected-subgraph DFS postorder

Compute the affected region first, then emit nodes by DFS-based reverse postorder.

Pros:

- linear work in the affected region
- compact traversal logic

Cons:

- stable tie-breaking is harder to reason about cleanly
- cycle witness extraction is less direct

## Approach family C: affected-subgraph stable Kahn pass

Compute the affected region first, restrict indegrees to that induced subgraph, and emit nodes from
a stable ready queue.

Pros:

- exact fit for the required affected-set contract
- deterministic order and uniqueness are easy to express as invariants
- failure condition is explicit when emitted-node count falls short

Cons:

- needs a secondary witness-extraction step on failure
- requires careful explanation of why unaffected cycles are irrelevant

## Approach family D: SCC condensation first

Collapse strongly connected components before ordering.

Pros:

- makes cycle structure explicit
- gives a direct witness path when cycles exist

Cons:

- more machinery than the common acyclic case needs
- easy to over-engineer if all the memo needs is a clear failure-path witness

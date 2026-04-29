# E3 Failure Traces

These synthetic traces summarize why the current heuristic is not acceptable.

## Trace F1: duplicate enqueue on join

Observed graph:

- `A -> C`
- `B -> C`

Changed set:

- `{A, B}`

Current heuristic:

- pushes `C` once after processing `A`
- pushes `C` again after processing `B`

Observed bad output:

- `A, B, C, C`

Required lesson:

- the memo must explain why a sound invariant prevents duplicate emission even when multiple changed
  predecessors converge.

## Trace F2: nondeterministic tie-breaking

Observed graph:

- `A -> D`
- `B -> D`
- `C -> D`

Changed set:

- `{A, B, C}`

Current heuristic:

- iterates the ready set with container order

Observed bad outputs across two machines:

- run 1: `A, B, C, D`
- run 2: `C, A, B, D`

Required lesson:

- the memo must name a stable tie-break rule and explain why it is part of correctness, not a
  cosmetic preference.

## Trace F3: irrelevant cycle blocks the whole run

Observed graph:

- affected component: `P -> Q -> R`
- unrelated component: `X -> Y -> X`

Changed set:

- `{P}`

Current heuristic:

- topologically sorts the full graph and halts on `X -> Y -> X`

Observed bad result:

- no rerun plan for `P, Q, R`

Required lesson:

- the memo must separate the affected subgraph from the global graph and explain why the unrelated
  cycle is not a blocker.

## Trace F4: empty changed set still emits work

Changed set:

- `{}`

Current heuristic:

- seeds the queue with all zero-indegree nodes

Observed bad output:

- every root node reruns even though nothing changed

Required lesson:

- the memo must handle the empty-input edge case explicitly.

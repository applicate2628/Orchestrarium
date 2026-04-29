# Invariant Set

The memo should make the correctness story explicit with invariants close to these:

- `I1` closure exactness: a node is in the affected set iff it is changed or reachable from a
  changed node
- `I2` ready-set soundness: an affected node is in the ready queue iff it has not been emitted and
  every affected predecessor has already been emitted
- `I3` unique emission: each affected node is emitted at most once even if multiple affected
  predecessors converge on it
- `I4` stable-order minimality: among all currently ready nodes, the emitted node has the minimal
  stable key, so equal inputs yield equal output order
- `I5` failure witness soundness: if not all affected nodes can be emitted, the remaining affected
  subgraph contains a directed cycle or self-dependency and the returned witness is drawn from that
  remainder

The exact wording can vary, but a passing memo should make these logical obligations explicit and
use them in the correctness sketch.

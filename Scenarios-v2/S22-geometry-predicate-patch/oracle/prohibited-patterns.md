# Prohibited Patterns

The following patterns should lose correctness or scope-discipline points:

- special-casing `scale-aware-collinear`, `endpoint-gap-within-tolerance`, or any other fixture case
  by name or literal coordinate tuple
- moving the fix into `candidate/graphics-renderer/`, `candidate/ui-overlays/`, or any other
  non-geometry root
- replacing the predicate with renderer, raster, or viewport heuristics
- globally inflating tolerances until `collinear-but-disjoint` or `near-collinear-outside-bbox`
  become false positives
- editing unrelated benchmark content to hide the failing behavior

# Intended Invariants

The patch is expected to preserve these invariants:

1. `orientation(a, b, c) == -orientation(a, c, b)` for non-collinear inputs
2. exact collinear triples remain collinear after the fix
3. interior crossing segments still intersect
4. endpoint contact and collinear overlap count as intersection when they are within the approved
   tolerance
5. near-collinear but clearly disjoint segments remain non-intersecting
6. the geometry layer remains the owning boundary; renderer, UI, and benchmark harness code stay
   untouched

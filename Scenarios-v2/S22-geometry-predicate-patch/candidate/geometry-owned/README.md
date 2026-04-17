# Geometry-Owned Root

This root represents the geometry team's owned seam for planar predicates.

## Owned files

- `src/geometry/predicates.py` implements orientation and segment-intersection predicates
- `tests/test_predicates.py` is the direct validation surface for this scenario

## Out of scope inside the bundle

- graphics or renderer behavior
- UI overlays or interaction semantics
- unrelated benchmark harness data

The expected fix is local: improve robustness for near-collinear and endpoint cases without
changing ownership or reaching across layers.

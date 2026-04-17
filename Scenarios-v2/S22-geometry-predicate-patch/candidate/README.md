# Candidate Root

This is the mutable run root copied for each scored execution.

The start state is intentionally wrong for scale-sensitive geometry. The predicate kernel in
`geometry-owned/` uses a fixed absolute epsilon and exact bounding-box checks, so it misses
deterministic near-collinear and endpoint-contact cases.

## Editable files

- `geometry-owned/src/geometry/predicates.py`
- `geometry-owned/tests/test_predicates.py`

## Read-only context inside the candidate root

- `geometry-owned/README.md`
- `graphics-renderer/`
- `ui-overlays/`
- `unrelated-benchmarks/`

The intended repair path is to keep the change inside the geometry-owned seam and validate it with
direct tests only.

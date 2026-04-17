# Task

You are acting as `$geometry-engineer` on an admitted `P05` specialty implementation phase.

## Goal

Repair the deterministic geometry predicate bug in `candidate/geometry-owned/` so the module
handles the failing near-collinear and endpoint cases without widening into rendering, UI, or
unrelated benchmark roots.

## Required output

Update these files only:

- `candidate/geometry-owned/src/geometry/predicates.py`
- `candidate/geometry-owned/tests/test_predicates.py`

## Geometry requirements

- preserve a right-handed 2D Cartesian convention (`+x` right, `+y` up)
- treat collinearity with a scale-aware signed-area tolerance rather than a fixed global cutoff
- count endpoint contact and collinear overlap as intersections when they are within the approved
  segment-span tolerance
- keep near-collinear but clearly disjoint cases non-intersecting
- keep the change inside the geometry-owned module and direct tests only

## Disallowed behavior

- do not edit `inputs/`, `oracle/`, or `verifiers/`
- do not move the fix into graphics, renderer, UI, or benchmark harness code
- do not special-case the case IDs from `failing-cases.json`
- do not replace the predicate with raster or renderer heuristics

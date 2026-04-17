# S22 Geometry Predicate Patch

`S22` benchmarks `R22 $geometry-engineer` on a bounded geometry-owned code patch. The candidate
must repair a deterministic 2D predicate bug in a local geometry kernel, keep edits inside the
geometry module and its direct tests, and validate the fix against tolerance-sensitive edge cases.

## Scenario summary

The candidate root contains a small non-rendering geometry package used by downstream systems but
owned entirely by the geometry layer. The start state mishandles three deterministic cases:

- large-scale near-collinear orientation that should collapse to `0`
- endpoint contact that should count as intersecting within the coordinate tolerance
- large-scale collinear overlap that should count as intersecting instead of separate

The fix must stay in the geometry-owned predicate module and direct tests only. Renderer, UI, and
unrelated benchmark roots are present as out-of-scope decoys.

## Expected candidate work

Edit only the files listed in `scenario.yaml`:

- `candidate/geometry-owned/src/geometry/predicates.py`
- `candidate/geometry-owned/tests/test_predicates.py`

Use the immutable inputs in `inputs/` to preserve the approved coordinate convention, tolerance
policy intent, and invariant set. The expected solution direction is:

1. keep the kernel in a right-handed 2D Cartesian frame
2. replace the fixed absolute area cutoff with a scale-aware collinearity check
3. reuse a segment-span coordinate tolerance for on-segment checks
4. preserve strict separation for truly disjoint or parallel cases
5. leave graphics, UI, and unrelated benchmark content untouched

## What this bundle tests

- geometry-owned robustness work without renderer or UI spillover
- deterministic handling of tolerances, degeneracies, and edge conditions
- scope discipline for a specialty implementation role
- local validation against direct tests and a broader oracle truth table

## Bundle map

- `inputs/` holds the immutable task contract, failing case packet, coordinate notes, and invariants
- `candidate/` is the mutable run root copied for each execution
- `oracle/` defines the truth table, tolerance policy, and scenario-specific scoring anchors
- `verifiers/` contains bundle-shape, start-state, solved-run, and scope-manifest checks

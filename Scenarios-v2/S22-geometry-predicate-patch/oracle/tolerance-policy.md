# Tolerance Policy

`S22` expects the geometry fix to preserve these local rules:

## Signed-area tolerance

For `orientation(a, b, c)`:

- compute `signed_area2 = cross(b - a, c - a)`
- compute `edge_scale_sq = max(|ab|^2, |ac|^2, |bc|^2, 1.0)`
- treat the triple as collinear when `abs(signed_area2) <= base_area_epsilon * edge_scale_sq`

The approved `base_area_epsilon` is `2.5e-10`.

## Coordinate tolerance

For collinear `on_segment(a, b, p)` checks:

- compute `segment_span = max(abs(b.x - a.x), abs(b.y - a.y), 1.0)`
- compute `coordinate_tolerance = base_coordinate_epsilon * segment_span`
- allow `p` to lie within `coordinate_tolerance` of the inclusive segment bounds on both axes

The approved `base_coordinate_epsilon` is `2.5e-10`.

## Ownership rule

These tolerances belong in the geometry-owned predicate module. They must not be reimplemented in
graphics, UI, or benchmark harness code.

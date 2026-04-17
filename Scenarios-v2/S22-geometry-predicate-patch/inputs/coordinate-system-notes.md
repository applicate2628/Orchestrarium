# Coordinate System Notes

- Space: planar 2D Cartesian
- Handedness: right-handed (`+x` points right, `+y` points up)
- Units: arbitrary but consistent; the cases intentionally mix unit-scale and million-scale spans
- Predicate sign: positive signed area is counter-clockwise, negative is clockwise, zero is
  collinear
- Tolerance intent: signed-area tolerance must scale with the largest triangle edge squared, and
  coordinate tolerance must scale with the segment span instead of using a single fixed cutoff

The scenario is deterministic. There is no randomness, viewport logic, renderer state, or UI
semantics in scope.

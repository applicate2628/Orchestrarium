# Scoring Anchors

`S23` uses the `implementation` score profile.

## High-signal pass conditions

- transparent draws sort back-to-front and preserve equal-depth insertion order
- transparent draws no longer write depth, so later emissive passes can still contribute when the
  depth test permits them
- additive draws accumulate light instead of behaving like alpha-over
- the opaque baseline cases still pass, so the fix is targeted rather than a renderer rewrite
- the diff stays inside `candidate/graphics-owned/` and its direct tests only

## High-signal failure conditions

- the candidate still fails any deterministic frame-oracle case
- the fix widens into Qt, web UI, geometry, visualization, or shared benchmark surfaces
- the candidate introduces screenshot or image-baseline maintenance outside the bundle
- the patch removes or weakens direct tests instead of fixing the renderer behavior

# Task

You are acting as `$graphics-engineer` on an admitted `P05` specialty implementation phase.

## Goal

Repair the bundle-local renderer in `candidate/graphics-owned/` so transparent and additive passes
produce the deterministic oracle frames without widening into Qt, web UI, geometry, visualization,
or shared benchmark surfaces.

## Required output

Update these files only:

- `candidate/graphics-owned/src/graphics_pipeline/renderer.py`
- `candidate/graphics-owned/tests/test_renderer.py`

## Graphics requirements

- opaque draws must remain depth-writing and render front-to-back by increasing depth value
- transparent draws must execute after opaque, preserve draw order within equal depth, and render
  back-to-front without writing depth
- additive draws must accumulate emission instead of using ordinary alpha-over compositing
- all frame outputs must stay deterministic and match the textual oracle anchors in `oracle/`
- keep validation local to the bundle; do not introduce screenshot baselines or external render
  harnesses

## Disallowed behavior

- do not edit `inputs/`, `oracle/`, or `verifiers/`
- do not move the fix into Qt, web UI, geometry, or visualization decoy roots
- do not special-case the case IDs from `oracle/frame-oracle.json`
- do not replace the bundle-local renderer with precomputed image files or screenshot maintenance

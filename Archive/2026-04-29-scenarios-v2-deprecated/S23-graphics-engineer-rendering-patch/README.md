# S23 Graphics Engineer Rendering Patch

`S23` benchmarks `R23 $graphics-engineer` on a bounded rendering-pipeline repair. The scored task
is to correct transparent-pass ordering, transparent depth-write policy, and additive emission
blending in a bundle-local software renderer without drifting into Qt, web UI, geometry,
visualization, or shared benchmark surfaces.

## Scenario summary

The mutable candidate root contains a tiny deterministic renderer with three start-state pipeline
bugs that matter for graphics work:

- transparent draws are processed near-to-far instead of back-to-front
- transparent draws incorrectly write depth and block later emission passes
- additive draws use ordinary alpha-over blending instead of emission accumulation

The bundle uses small RGBA frame anchors in JSON rather than screenshot baselines or external image
fixtures.

## Expected candidate work

Edit only the files listed in `scenario.yaml`:

- `candidate/graphics-owned/src/graphics_pipeline/renderer.py`
- `candidate/graphics-owned/tests/test_renderer.py`

Use the immutable packet in `inputs/` to preserve the intended stage order, depth behavior, and
bundle boundary. The expected local validation flow after a repair is:

1. run `python tests/test_renderer.py` from `candidate/graphics-owned/`
2. run `python verifiers/run_graphics_checks.py` from the bundle root
3. use `python verifiers/check_scope.py --changed-path ...` to confirm the diff stayed in bounds

## What this bundle tests

- graphics-pipeline reasoning instead of Qt, DOM, or chart semantics
- deterministic blending and stage-order correctness with textual framebuffer anchors
- scope discipline for a specialty implementation role
- validation without screenshot-baseline maintenance outside the bundle

## Bundle map

- `inputs/` holds the immutable task contract, render intent, boundary notes, and expected
  start-state failures
- `candidate/` is the mutable run root copied for each execution
- `oracle/` defines the bundle contract, deterministic frame oracle, widening prohibitions, and
  scoring anchors
- `verifiers/` contains bundle-shape, start-state, completed-run, and scope checks

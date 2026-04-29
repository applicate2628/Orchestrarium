# Task

You are acting as `$visualization-engineer` on an admitted `P05` specialty implementation phase.

## Goal

Repair the bundle-local interpretation encoder in `candidate/visualization-owned/` so the emitted
section specs preserve signed anomaly meaning, depth orientation, and explicit missing-data gaps
without widening into graphics-pipeline, Qt, model-view, scorer, or shared benchmark surfaces.

## Required output

Update these files only:

- `candidate/visualization-owned/src/visualization_owned/anomaly_section.py`
- `candidate/visualization-owned/tests/test_anomaly_section.py`

## Visualization requirements

- keep the color scale zero-centered with a signed diverging interpretation
- map shallower depths to smaller `y_index` values and deeper depths lower in the section
- preserve missing samples as entries in `gaps`, not synthetic neutral cells
- keep the emitted spec deterministic and aligned with `oracle/encoding-oracle.json`
- keep validation local to the bundle; do not introduce screenshots, GUI harnesses, or shared
  scoring hooks

## Disallowed behavior

- do not edit `inputs/`, `oracle/`, or `verifiers/`
- do not move the fix into graphics-pipeline, Qt, model-view, or scorer decoy roots
- do not special-case the case IDs from `inputs/section-cases.json`
- do not solve the scenario by replacing the builder with precomputed oracle payloads

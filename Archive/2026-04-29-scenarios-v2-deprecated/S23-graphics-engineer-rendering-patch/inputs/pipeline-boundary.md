# Pipeline Boundary

The owned seam for this scenario is `candidate/graphics-owned/` only.

## Read-only decoy roots inside the candidate bundle

- `candidate/qt-preview-pane/` is a desktop UI decoy; do not widen into Qt widgets or dialogs
- `candidate/web-preview-shell/` is a browser UI decoy; do not widen into DOM, CSS, or Playwright
- `candidate/geometry-kernel/` is a geometry decoy; do not move the fix into predicate or
  transform ownership
- `candidate/visualization-lab/` is a visualization decoy; do not turn the task into chart or
  data-interpretation work

Do not edit existing scenario roots, shared verifiers, or any screenshot-baseline machinery outside
this bundle. The bundle must stay self-contained.

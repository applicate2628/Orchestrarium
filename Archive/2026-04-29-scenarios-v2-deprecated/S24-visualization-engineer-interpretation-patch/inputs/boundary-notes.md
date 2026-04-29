# Boundary Notes

The owned seam for this scenario is `candidate/visualization-owned/` only.

## Read-only decoy roots inside the candidate bundle

- `candidate/graphics-pipeline/` is a graphics decoy; do not widen into framebuffer or staged
  rendering ownership
- `candidate/qt-legend-pane/` is a Qt decoy; do not move the fix into widgets, focus handling, or
  desktop dialog code
- `candidate/model-view-adapter/` is a model/view decoy; do not translate the task into proxy
  models, delegates, or view synchronization
- `candidate/scorer-hooks/` is a scorer decoy; do not alter metadata, score profiles, or benchmark
  evaluation contracts

Do not edit existing scenario roots, shared planning docs, or any scorer or runner outside this
bundle. The bundle must stay self-contained.

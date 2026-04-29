# Forbidden Widening

- Do not reopen graphics-pipeline, staged-rendering, or framebuffer surfaces; `S24` is not `S23`.
- Do not translate the fix into Qt widgets, dialogs, legend panes, or desktop focus behavior;
  `S24` is not `S17`.
- Do not move interpretation logic into model/view adapters, proxy models, delegates, or view
  synchronization; `S24` is not the future `S18`.
- Do not modify scorer hooks, `scenario.yaml`, or any benchmark metadata to excuse a wrong emitted
  spec.
- Do not introduce screenshot baselines, GUI automation, or shared fixtures outside this bundle.

# Inputs

This directory is the immutable packet for the `S16` frontend scenario. It provides the scoped web
UI task, the state and accessibility contract, and the observed browser failures the candidate must
repair.

## Included materials

- `task.md` defines the benchmark task and the allowed edit surface
- `ui-state-contract.md` describes the required loading, success, empty, and error behavior
- `accessibility-notes.md` captures semantic, labeling, and focus expectations
- `failing-browser-observations.md` records the broken start state from the local preview
- `component-scope.md` separates editable UI files from read-only preview and verification material

These inputs are web-specific. A generic implementation answer that widens into server behavior,
desktop UI, framework churn, or scorer edits should lose scope-discipline points.

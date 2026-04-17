# Candidate Root

This is the mutable run root copied for each scored execution.

The start state is intentionally wrong for visualization interpretation work. The builder in
`visualization-owned/` collapses signed anomalies into warm-only tokens, flips the depth axis, and
fills missing observations as neutral cells.

## Editable files

- `visualization-owned/src/visualization_owned/anomaly_section.py`
- `visualization-owned/tests/test_anomaly_section.py`

## Read-only context inside the candidate root

- `visualization-owned/README.md`
- `graphics-pipeline/`
- `qt-legend-pane/`
- `model-view-adapter/`
- `scorer-hooks/`

The intended repair path is to keep the change inside the visualization-owned seam and its direct
verification file only.

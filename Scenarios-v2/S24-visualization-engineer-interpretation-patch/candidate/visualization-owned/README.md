# Visualization-Owned Root

This bundle-local subtree represents the visualization team's owned seam for a deterministic section
spec builder.

## Local layout

- `src/visualization_owned/anomaly_section.py` is the editable interpretation encoder
- `src/visualization_owned/__init__.py` is the read-only package entrypoint
- `tests/test_anomaly_section.py` is the editable direct verification file

## Local validation

From this directory:

- run `python tests/test_anomaly_section.py`

This candidate stays intentionally non-web and non-Qt. There is no graphics-pipeline ownership, no
desktop widget stack, no model/view adapter seam, and no scorer-control surface in this subtree.

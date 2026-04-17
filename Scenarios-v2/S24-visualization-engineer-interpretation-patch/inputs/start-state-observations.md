# Start-State Observations

The bundled candidate root is expected to fail exactly these deterministic oracle cases before any
repair is applied:

- `signed-anomaly-encoding`: the emitted color scale is not zero-centered and negative anomalies are
  encoded as warm cells
- `depth-axis-descends`: `y_index` values are inverted so deep samples appear above shallow samples
- `missing-samples-remain-gaps`: missing samples are turned into neutral cells instead of explicit
  gap records

The bundle should still preserve station ordering and deterministic label formatting in the
non-failing parts of the emitted spec.

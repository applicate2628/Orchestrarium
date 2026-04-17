# Interpretation Brief

The section packets model anomaly values relative to a baseline climatology.

## Encoding semantics

- `anomaly_limit_deg_c` is the absolute extent of the diverging scale, so the valid color domain is
  `[-limit, +limit]`
- `0.0` is the center of the palette and must remain the neutral reference
- values with absolute magnitude below `0.25 degC` should emit `neutral`
- otherwise quantize by thirds of the declared limit:
  - `<= limit / 3` -> `cool-1` or `warm-1`
  - `<= 2 * limit / 3` -> `cool-2` or `warm-2`
  - `> 2 * limit / 3` -> `cool-3` or `warm-3`
- negative anomalies are cooler-than-baseline encodings and positive anomalies are
  warmer-than-baseline encodings

## Layout semantics

- `depth_levels_m` is already ordered from shallow to deep
- the section is scientific, so depth increases downward: the shallowest depth gets `y_index: 0`
- the builder should preserve station order as given in the packet
- missing samples stay absent from `cells` and appear only in `gaps` with their reason

## Non-goals

- do not reinterpret the task as framebuffer blending or draw-order repair
- do not add Qt widgets, legends, or model/view adapters to carry the semantics
- do not modify benchmark metadata, score weights, or scenario contracts to make the output pass

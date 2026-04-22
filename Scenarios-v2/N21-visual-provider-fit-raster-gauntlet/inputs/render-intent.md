# Render Intent

The panel is a small deterministic raster diagnostic:

- Background is `#111318`.
- Heatmap cells are fixed-size rectangles with one-pixel gaps.
- `null` values represent sparse missing data and remain background-colored.
- The selected cell is visually above the heatmap, with a yellow focus ring and an additive center
  highlight.
- The legend is a vertical two-pixel-wide strip ordered `-2, -1, 0, 1, 2`.
- Annotation cue pixels are last-write overlays.

This is intentionally a pixel oracle rather than a prose review. The verifier checks real rendered
pixels and PPM metadata.

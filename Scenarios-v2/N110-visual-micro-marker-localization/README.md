# N110 Visual Micro-Marker Localization

Diagnostic W88 for `L08` / `L12`: pixel-level visual grounding on tiny UI-like markers.

The task gives one `2200 x 1600` raster with six unique `13 x 13` colored markers. The candidate must return exact center coordinates as JSON. The verifier uses a several-pixel tolerance (`mean <= 8 px`, `max <= 14 px`) rather than a zero-pixel oracle, but still rejects coarse localization.

This is not a semantic screenshot-review task and not an output-budget task. It isolates fine-grained coordinate grounding: a capability expected to affect UI/image work where small targets, hit boxes, dense overlays, or pixel anchors matter.

Required output:

```json
{
  "image_id": "N110-visual-micro-marker-canvas-v1",
  "points": {
    "red": {"x": 0, "y": 0},
    "cyan": {"x": 0, "y": 0},
    "lime": {"x": 0, "y": 0},
    "magenta": {"x": 0, "y": 0},
    "amber": {"x": 0, "y": 0},
    "blue": {"x": 0, "y": 0}
  }
}
```

## Terms and Abbreviations

- `JSON`: JavaScript Object Notation; the machine-readable answer format.
- `L08`: RF12 visual/graphics worker lane.
- `L12`: RF12 UI visual-correctness review lane.
- `RF12`: the current role-fit twelve-line benchmark routing surface.
- `UI`: User Interface.
- `W88`: the hardening wave identifier for this diagnostic.

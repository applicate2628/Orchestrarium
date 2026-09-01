# Task

You are given one image:

- image id: `N110-visual-micro-marker-canvas-v1`
- dimensions: `2200 x 1600`
- coordinate origin: top-left pixel
- x increases to the right; y increases downward
- all returned coordinates must be in the original `2200 x 1600` pixel space

Important coordinate-frame rule: if your image viewer, model runtime, or tool displays a resized copy
of the image, do not return display-space coordinates. Scale any observed coordinates back to the
original `2200 x 1600` image dimensions before returning JSON.

Locate the center pixel of each visible `13 x 13` solid color marker:

- `red`
- `cyan`
- `lime`
- `magenta`
- `amber`
- `blue`

Return exactly one coordinate for each listed color. Use integer pixel coordinates. Do not return alternate candidates, duplicate colors, confidence notes, ranges, bounding boxes, or commentary.

Return only JSON:

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

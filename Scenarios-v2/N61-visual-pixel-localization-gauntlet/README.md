# N61 Visual Pixel Localization Gauntlet

This diagnostic scenario measures visual perception for tiny UI/image targets.
It is intentionally separate from code-patch visual-raster scenarios: the worker
must inspect the attached image and return pixel-center coordinates for the
requested targets.

The benchmark is scoreable through `verifiers/check_visual_localization.py`.
Runtime wrappers should attach `inputs/visual-localization-canvas.png` as image
context where the provider supports image input. If a provider route cannot
attach or otherwise expose the image to the model, classify that run as
`NOT-RUN/unsupported-visual-route`, not as a model failure.

Expected answer shape:

```json
{
  "image_id": "N61-visual-localization-canvas-v1",
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

Only integer pixel coordinates are scored. The image origin is top-left.
The object-map answer shape is intentional: it prevents duplicate-id candidate
lists from masquerading as a complete answer.

# Task

You are given one image:

- image id: `N61-visual-localization-canvas-v1`
- dimensions: `2200 x 1600`
- coordinate origin: top-left pixel
- x increases to the right; y increases downward
- minor grid spacing: 20 px
- major grid spacing: 100 px

Locate the center pixel of each 13 x 13 solid target square:

- `red`
- `cyan`
- `lime`
- `magenta`
- `amber`
- `blue`

Ignore same-color decoys that are not 13 x 13 solid squares. Return exactly
one coordinate for each listed color. Do not return alternate candidates,
duplicate colors, ranked guesses, or commentary. If more than one same-color
mark is visible, choose the one that is the 13 x 13 solid target square.

Return only JSON:

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

Use integer pixel coordinates. Do not include commentary.

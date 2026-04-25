# Task

You are reviewing one dashboard screenshot for visual correctness.

- image id: `N68-actual-screenshot-v1`
- image file: `actual-screenshot.png`
- dimensions: `1280 x 900`
- coordinate origin: top-left pixel
- x increases to the right; y increases downward

Find exactly eight real visual defects. Return only JSON. Do not include markdown, commentary, or
alternate candidates.

For each finding, include:

- `component`: concise visible component name
- `defect`: concise defect class
- `x` and `y`: approximate center pixel of the visible defect
- `evidence`: short visual cue from the screenshot

Do not flag intentional visual states:

- decorative background/grid lines
- disabled Export button
- muted timestamp/meta text

Return JSON in this shape:

```json
{
  "image_id": "N68-actual-screenshot-v1",
  "findings": [
    {
      "component": "component name",
      "defect": "defect class",
      "x": 0,
      "y": 0,
      "evidence": "visual cue"
    }
  ],
  "non_findings": [
    "decorative background/grid lines",
    "disabled Export button",
    "muted timestamp/meta text"
  ]
}
```

# Task

You are reviewing a UI screenshot diff for visual regressions.

- image id: `N98-visual-regression-diff`
- baseline image: `baseline.png`
- current image: `current.png`
- dimensions: `1400 x 900`
- coordinate origin: top-left pixel
- x increases right; y increases downward

Find exactly eight regressions visible in `current.png` relative to `baseline.png`. Return only
JSON. Do not include markdown, commentary, alternate candidates, or broad UX advice.

For each finding, include:

- `id`: one of `V01` through `V08`
- `component`: concise visible component name
- `defect`: concise defect class
- `severity`: one of `high`, `medium`, or `low`
- `x` and `y`: approximate center pixel of the visible defect in `current.png`
- `evidence`: short visual cue from the screenshot pair

Do not flag intentional non-findings. Copy these exact five strings into `non_findings`:

- `decorative grid/background lines`
- `disabled Export button`
- `muted timestamp/meta text`
- `brand logo/header mark`
- `skeleton shimmer placeholder`

Return JSON in this shape:

```json
{
  "image_id": "N98-visual-regression-diff",
  "findings": [
    {
      "id": "V01",
      "component": "component name",
      "defect": "defect class",
      "severity": "medium",
      "x": 0,
      "y": 0,
      "evidence": "visual cue"
    }
  ],
  "non_findings": [
    "decorative grid/background lines",
    "disabled Export button",
    "muted timestamp/meta text",
    "brand logo/header mark",
    "skeleton shimmer placeholder"
  ]
}
```

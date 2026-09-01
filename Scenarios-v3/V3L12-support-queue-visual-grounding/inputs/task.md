# Task

You are reviewing one high-resolution support-ticket triage console screenshot for visual
correctness.

- image id: `V3L12-support-queue-visual-grounding`
- image file: `actual-screenshot.png`
- dimensions: `1600 x 1000`
- coordinate origin: top-left pixel
- x increases to the right; y increases downward

Find exactly ten real visual defects. Return only JSON. Do not include markdown, commentary, or
alternate candidates.

For each finding, include:

- `component`: concise visible component name
- `defect`: concise defect class
- `severity`: one of `high`, `medium`, or `low`
- `x` and `y`: approximate center pixel of the visible defect, not the whole component
- `evidence`: short visual cue from the screenshot

Do not flag intentional visual states:

- decorative background/grid lines
- disabled Export CSV button
- muted timestamp/meta text
- decorative response-time sparkline
- skeleton shimmer placeholder
- the brand mark or header ornament

Return JSON in this shape:

```json
{
  "image_id": "V3L12-support-queue-visual-grounding",
  "findings": [
    {
      "component": "component name",
      "defect": "defect class",
      "severity": "medium",
      "x": 0,
      "y": 0,
      "evidence": "visual cue"
    }
  ],
  "non_findings": [
    "decorative background/grid lines",
    "disabled Export CSV button",
    "muted timestamp/meta text",
    "decorative response-time sparkline",
    "skeleton shimmer placeholder",
    "brand mark/header ornament"
  ]
}
```

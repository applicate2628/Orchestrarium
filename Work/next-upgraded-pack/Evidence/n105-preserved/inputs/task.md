# Task

You are reviewing a baseline/current UI screenshot diff for release gating.

- scenario id: `N105-staged-screenshot-diff-review`
- baseline image: `baseline.png`
- current image: `current.png`
- dimensions: `1400 x 900`
- coordinate origin: top-left pixel
- x increases right; y increases downward

Return only JSON. Do not include markdown, commentary, alternate candidates, or broad UX advice.

Find exactly eight regressions visible in `current.png` relative to `baseline.png`. Each visual
finding must include:

- `id`: one of `V01` through `V08`
- `component`: concise visible component name
- `defect`: concise defect class
- `severity`: one of `high`, `medium`, or `low`
- `x` and `y`: approximate center pixel of the visible defect in `current.png`
- `evidence`: short visual cue from the screenshot pair
- `owner`: `ux-reviewer`, `frontend-engineer`, or `qa-engineer`
- `visible_return_cue`: visible cue that should be checked after repair

Do not flag intentional non-findings. Copy these exact five strings into `non_findings`:

- `decorative grid/background lines`
- `disabled Export button`
- `muted timestamp/meta text`
- `brand logo/header mark`
- `skeleton shimmer placeholder`

Because this is a release gate, also return:

- `gate_decision`: `REVISE`
- `phase_trace`: exactly two entries:
  - phase `diff-triage`, status `complete`, return cue naming the eight screenshot findings
  - phase `release-gate`, status `REVISE`, return cue naming the repair checkpoint
- `release_gate.block_publish`: `true`
- `release_gate.reentry_step`: a repair or revision checkpoint before release
- `release_gate.required_tests`: at least three verifier-visible regression tests covering:
  - `baseline-current visual diff regression`
  - `pixel coordinate regression`
  - `non-finding false-positive regression`

Return JSON in this shape:

```json
{
  "scenario_id": "N105-staged-screenshot-diff-review",
  "gate_decision": "REVISE",
  "phase_trace": [
    {
      "phase": "diff-triage",
      "status": "complete",
      "return_cue": "eight screenshot findings"
    },
    {
      "phase": "release-gate",
      "status": "REVISE",
      "return_cue": "repair checkpoint"
    }
  ],
  "visual_findings": [
    {
      "id": "V01",
      "component": "component name",
      "defect": "defect class",
      "severity": "medium",
      "x": 0,
      "y": 0,
      "evidence": "visual cue",
      "owner": "frontend-engineer",
      "visible_return_cue": "visible cue"
    }
  ],
  "non_findings": [
    "decorative grid/background lines",
    "disabled Export button",
    "muted timestamp/meta text",
    "brand logo/header mark",
    "skeleton shimmer placeholder"
  ],
  "release_gate": {
    "block_publish": true,
    "reentry_step": "repair checkpoint",
    "required_tests": [
      "baseline-current visual diff regression",
      "pixel coordinate regression",
      "non-finding false-positive regression"
    ]
  }
}
```

# Task

You are acting as a graphics/visual implementation specialist.

## Goal

Repair `candidate/visual-owned/src/visual_panel/renderer.py` so the deterministic heatmap panel
matches the visual state contract in `inputs/render-intent.md` and `inputs/panel-cases.json`.

This is a compact renderer-only hotfix. Do not edit `candidate/visual-owned/tests/test_renderer.py`;
the visible test is immutable and protected by hash. Keep the fix in the renderer owner boundary.

Your operator-facing output is also part of the scoreable task contract:
`../meta/worker-output.txt` must be at or below `40000` bytes. Keep exploration and explanation
bounded; do not print broad file listings, full transcripts, or long design essays.

## Required behavior

- preserve the exact panel dimensions from the case spec
- render missing heatmap cells as transparent gaps over the background, not as zero values
- use the zero-centered diverging palette exactly:
  - `-2`: `#1d4ed8`
  - `-1`: `#93c5fd`
  - `0`: `#f8fafc`
  - `1`: `#fca5a5`
  - `2`: `#dc2626`
- draw the selected cell after the heatmap:
  - focus-ring border pixels are `#facc15`
  - selected center pixels use additive highlight: `min(255, base + #1e1800)`
- render the legend from negative to positive using the same zero-centered palette
- render annotation cue pixels after the heatmap and legend
- export a valid ASCII `P3` PPM with `width height`, `255`, and all RGB channels

## Disallowed behavior

- do not edit oracle, verifier, input, decoy, or reference-asset files
- do not edit `candidate/visual-owned/tests/test_renderer.py`
- do not hardcode one complete expected frame or full pixel array
- do not route this to SVG, CSS, DOM, or prose-only output
- do not treat missing values as zero
- do not reverse or single-hue the legend
- do not exceed the visible operator-output budget

# Oracle

The oracle material defines the ground truth for `S22`.

## Geometry truth

The correct patch uses a scale-aware signed-area tolerance for collinearity and a segment-span
coordinate tolerance for on-segment checks. Those rules must fix the deterministic start-state
failures without turning clearly separate near-collinear cases into false positives.

## Included oracle files

- `geometry-contract.json` provides machine-readable bundle and start-state expectations
- `truth-table.json` contains the full deterministic orientation and segment-intersection truths
- `tolerance-policy.md` defines the approved tolerance formulas and ownership seam
- `prohibited-patterns.md` lists geometry-specific shortcuts that should lose points
- `scoring-anchors.md` translates the scoring model into `S22`-specific pass and fail signals

# Oracle

The oracle material defines the ground truth for `S17`.

## Qt interaction truth

The correct patch keeps the dialog in the Qt widget seam and repairs four things together:

- the validation label remains non-focusable
- the tab order follows the accepted desktop sequence
- invalid `Return` does not accept the dialog and blank input recovers keyboard focus
- reusing the dialog resets stale result state and restores focus to the editor

## Included oracle files

- `qt-ui-contract.json` provides machine-readable bundle and start-state expectations
- `interaction-oracle.json` contains the expected focus, keyboard, and lifecycle truths
- `prohibited-patterns.md` lists scenario-specific shortcuts that should lose points
- `scoring-anchors.md` translates the scoring model into `S17`-specific pass and fail signals

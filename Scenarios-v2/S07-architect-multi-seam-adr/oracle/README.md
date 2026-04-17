# Oracle

The oracle material defines the ground-truth architecture contract for `S07`.

## Decision truth

The admissible seam is the bundle-local oracle and verifier seam. The accepted constraints require
scenario-specific architect rules to stay local to the bundle instead of reopening the universal
metadata schema or central scorer behavior.

## Included oracle files

- `design-contract.json` provides machine-readable bundle and design-package anchors for the
  verifier
- `admissible-seams.md` explains the accepted seam and why the other seams lose points
- `anti-patterns.md` lists role-drift and contract-breaking patterns
- `scoring-anchors.md` translates the scoring model into `S07`-specific pass and fail signals

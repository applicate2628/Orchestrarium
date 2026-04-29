# Oracle

The oracle material defines the ground-truth security shape for `S12`.

## Expected read

The correct package stays in the security-engineer lane and anchors the analysis in the supplied
evidence. A strong answer identifies the five trust boundaries, carries the six required control
anchors, names the must-fix items implied by the dry-run evidence, and leaves the design in
`REVISE` until those constraints are accepted into the implementation plan.

## Included oracle files

- `security-constraint-contract.json` provides machine-readable verifier anchors
- `expected-boundaries.md` describes the boundary set that must appear in a passing package
- `required-controls.md` lists the control anchors and their evidence basis
- `prohibited-patterns.md` lists role drift and hand-waving failures
- `scoring-anchors.md` translates the scoring model into `S12`-specific pass and fail signals

# Oracle

The oracle material defines the ground-truth scientific read for `S11`.

## Expected read

The correct memo stays in the computational-scientist lane and anchors the analysis in the
supplied evidence. A strong answer writes the draft lumped-capacitance energy balance explicitly,
checks the parameter signs and units, notes that the aluminum block itself is compatible with a
single-state internal assumption, and then shows that the current fixed-loss model validates
Profile A but fails the full admitted range because Profile B exposes a fan-regime change and
sensor-lag limitations. The final gate decision should be `REVISE` because the current model is not
fully validated across the admitted use packet.

## Included oracle files

- `model-validation-contract.json` provides machine-readable verifier anchors
- `expected-model-read.md` describes the expected interpretation and disposition
- `validation-and-invariant-anchors.md` lists the expected equations, invariants, and limits
- `prohibited-patterns.md` lists role-drift and scope-break failures
- `scoring-anchors.md` translates the scoring model into `S11`-specific pass and fail signals

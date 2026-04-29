# Oracle

The oracle material defines the ground-truth repair for `S20`.

## Repair truth

The correct fix stays entirely inside the bundle-local platform-owned config seam. The repaired
collector and deployment config should agree on `/metrics`, the canonical OTLP endpoint, and the
required platform resource attributes while leaving backend, toolchain, runner, routing, and
results surfaces untouched.

## Included oracle files

- `platform-contract.json` provides machine-readable bundle and validation anchors
- `expected-patch.md` describes the required platform repair shape
- `forbidden-widening.md` lists out-of-scope edits that should lose correctness or scope points
- `scoring-anchors.md` turns the scoring model into `S20`-specific pass and fail signals

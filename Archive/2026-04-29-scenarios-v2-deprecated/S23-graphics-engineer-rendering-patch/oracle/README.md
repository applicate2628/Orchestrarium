# Oracle

The oracle material defines the ground truth for `S23`.

## Rendering truth

The correct patch preserves the existing opaque-depth baseline while fixing three graphics-pipeline
semantics:

- transparent draws sort back-to-front
- transparent draws do not stamp the depth buffer
- additive draws accumulate emissive color

## Included oracle files

- `graphics-contract.json` provides the machine-readable bundle and start-state contract
- `frame-oracle.json` contains the deterministic render scenes, expected frame outputs, and anchor
  pixels
- `forbidden-widening.md` lists graphics-specific scope violations that should lose points
- `scoring-anchors.md` translates the implementation score profile into `S23`-specific pass and
  fail signals

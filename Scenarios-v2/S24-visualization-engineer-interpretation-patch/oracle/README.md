# Oracle

The oracle material defines the ground truth for `S24`.

## Visualization truth

The correct patch preserves the section packets exactly while fixing three interpretation semantics:

- signed anomalies stay on a zero-centered diverging scale
- depth indices descend with increasing depth
- missing samples remain explicit gaps instead of synthetic neutral fills

## Included oracle files

- `visualization-contract.json` provides the machine-readable bundle and start-state contract
- `encoding-oracle.json` contains the deterministic expected section specs for each input case
- `forbidden-widening.md` lists visualization-specific scope violations that should lose points
- `scoring-anchors.md` translates the implementation score profile into `S24`-specific pass and
  fail signals

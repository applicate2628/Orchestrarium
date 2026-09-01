# V4C04 Verifier Contract

Each review area is an independent 10-point severity-weighted F1 atom. Findings match one-to-one by
normalized file, symbol, and severity; narrative does not participate. A location reported at the
wrong severity is unmatched. Duplicate or unsupported findings lower precision without erasing
matched recall. Evidence, non-findings, review scope, and actions score in separate atoms. Every
semantic atom is commitment-bearing: a present false positive, incompatible finding, wrong source,
wrong scope token, or wrong action activates the declared score-40 cap; missing answers retain
ordinary partial credit. The visible schema uses typed identifier, token, path, and symbol forms so
denial prose cannot ride inside a scored structure.

Scorer-side faults return `SCORER-ERROR` with no numeric score.

## Terms and Abbreviations

- `F1`: harmonic mean of precision and recall.
- `FAIL-COMMITMENT`: diagnostic status for a wrong present structured commitment.

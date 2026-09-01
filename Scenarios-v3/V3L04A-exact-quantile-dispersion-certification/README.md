# V3L04A - Exact Quantile And Dispersion Certification

Target line: `L04` (algorithm-scientist / numerical-stability). Second pure-algorithmic slot
alongside N22 (build-plan F5 / A5).

The candidate certifies, for six adversarial integer streams, the exact `p99`, `iqr`, and
`population_stddev`, plus a gate verdict, under explicitly-declared non-default conventions:
one-based upper-rank percentiles (no interpolation), population variance (divide by n), and
offset-shifted / exact accumulation for numerical stability. A hidden numeric oracle re-derives
every case number from `inputs/streams.json`; there is no answer key to copy.

## Why this separates near-peer strong models (not merely hard)

Every case is engineered so a strong-but-slightly-weaker convention choice yields a different
exact number, and three cases flip the gate verdict:

- upper-rank vs linear-interpolation percentiles (p99 and IQR),
- population vs sample (Bessel) variance,
- exact/offset-shifted vs naive fixed-precision dispersion (catastrophic cancellation at ~1e9).

## No physics

There is no electromagnetic or other physics model. Separation rests entirely on algorithmic
convention adherence and numerical-stability awareness, so a physics-solver strength cannot mask
algorithmic weakness (the confound this slot exists to remove from the L04 read).

## Layout

- `inputs/` - task, streams (authority), candidate methods, hard constraints, stale note.
- `candidate/` - the two editable files (memo + witness) in a failing start state.
- `oracle/` - contract, scoring anchors, and a passing `reference/` answer.
- `verifiers/check_quantile_dispersion.py` - deterministic, read-only, executes no candidate code.

## Terms and Abbreviations

- `p99` / `IQR` - 99th percentile / interquartile range (p75 - p25).
- `upper-rank` - percentile at one-based rank `ceil(p * n)`, no interpolation.
- `population variance` - summed squared deviations divided by n (not n - 1).
- `L04` - the algorithm/scientist routing line of the RF12 scorecard.

# Oracle

`quantile-dispersion-contract.json` holds the conventions, thresholds, required phrases/sections/
tables, and disallowed markers. It does NOT store the per-case answer numbers: the verifier
`check_quantile_dispersion.py` re-derives `p99`, `iqr`, `population_stddev`, gate verdict, and
failure reasons from `inputs/streams.json` using exact arithmetic (integer histogram ranks,
`fractions.Fraction` variance, `decimal.Decimal.sqrt`). So a leaked oracle does not reveal the
case answers - the candidate must compute them under the declared conventions.

`reference/` holds a passing reference answer (memo + witness) used for the admission reference
probe and for the four-probe regression. It is never staged to the provider-visible root.

Separation design (near-peer, not merely hard): every case is engineered so a strong-but-slightly-
weaker convention choice produces a different exact number, and three cases flip the gate verdict:

- `p99-rank-vs-interpolation-flip` - upper-rank p99 is 200 (PASS); linear interpolation reports >200 (FAIL).
- `population-vs-sample-stddev-flip` - population stddev 3.201562 (PASS); sample stddev 3.507136 (FAIL).
- `iqr-interpolation-consistency` - upper-rank IQR is 30; interpolated quartiles give 35 (and the
  interpolation-plus-sample path flips this case too).
- `large-offset-cancellation-stability` - exact population stddev 2.910708; naive fixed-precision
  sum-of-squares reports 11.31 (or 0) under catastrophic cancellation.

No physics: separation rests entirely on percentile-rank convention, population-vs-sample variance,
and offset-shift numerical stability, so a physics-solver strength cannot mask algorithmic weakness.

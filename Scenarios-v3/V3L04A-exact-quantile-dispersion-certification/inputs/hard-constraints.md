# Hard Constraints

These constraints fix the conventions and the gate limits. They are policy; the case numbers
come only from `inputs/streams.json`.

## Exactness

- Percentiles use one-based upper-rank: `rank = ceil(p * n)`, no interpolation.
- `iqr = p75 - p25` under the same convention.
- Dispersion uses population variance (divide by n). Sample (Bessel) variance is not admissible.
- `population_stddev` is reported to six decimal places, round-half-up.

## Memory

- A production stream can carry up to 10^9 observations. The chosen method must not materialize the
  full sample list for percentiles; it must operate on the bounded histogram.

## Numerical stability

- Dispersion shards can carry a common offset of order 10^9. Fixed-precision `E[x^2] - E[x]^2`
  cancels catastrophically at that scale. Shift out the offset (variance is translation invariant)
  or accumulate exactly.

## Gate limits

- p99 latency gate `<= 200ms`.
- iqr dispersion gate `<= 60ms`.
- population stddev gate `<= 3.500000`.
- A case FAILs if any single gate is exceeded; the `failure_reasons` list names each exceeded gate.

## Source authority

- `inputs/streams.json` is the only authority for case numbers.
- `inputs/stale-benchmark-note.md` is stale and cannot override the current streams.

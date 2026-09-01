# Quantile And Dispersion Certification Memo

## Decision

Decision: Method S - exact bounded-histogram percentiles plus population dispersion via offset-shifted exact summation

The release gate is decided on exact order statistics of the observed stream and on
the population dispersion of the dispersion shards. Method S computes percentiles
directly from the bounded integer histogram (no sample materialization, so a stream
of 10^9 observations is handled in memory proportional to the distinct-value count)
and computes dispersion by shifting out the common offset before an exact rational
summation.

## Convention Ledger

- percentile convention: rank = ceil(p * n), one-based, no interpolation
- variance convention: population divide by n, not sample divide by n minus 1
- large fixed offsets require offset-shifted or exact-rational accumulation
- stale benchmark notes cannot override the current input streams

| Source | Current signal | Decision use | Non-authority boundary |
|---|---|---|---|
| inputs/streams.json | per-case histogram and dispersion shards | sole authority for every case number | none; this is the input of record |
| inputs/hard-constraints.md | gate thresholds and conventions | fixes rank rule and divide-by-n | thresholds are gate limits, not stream data |
| inputs/stale-benchmark-note.md | a prior interpolation-based note | discarded | stale; cannot override the current streams |

Gate limits held for every case: p99 latency gate <= 200ms; iqr dispersion gate <= 60ms;
population stddev gate <= 3.500000.

## Rejected Methods

- Reject Method P - linear-interpolation percentiles (R type 7 / library default): interpolating
  between order statistics can move a near-boundary p99 across the 200ms line and flip the gate.
- Reject Method Q - sample variance (Bessel-corrected, divide by n minus 1): the gate measures the
  population dispersion of the observed stream, and the Bessel correction inflates near-boundary cases.
- Reject Method R - naive sum-of-squares dispersion in fixed precision: E[x^2]-E[x]^2 on samples with a
  ~1e9 offset cancels catastrophically and reports a wrong or zero spread.

## Case Witness Summary

| Case | p99 | IQR | Population stddev | Gate verdict |
|---|---|---|---|---|
| p99-rank-vs-interpolation-flip | 200 | 0 | 2.236068 | PASS |
| population-vs-sample-stddev-flip | 150 | 0 | 3.201562 | PASS |
| large-offset-cancellation-stability | 205 | 0 | 2.910708 | FAIL |
| iqr-interpolation-consistency | 90 | 30 | 3.415650 | PASS |
| stddev-gate-exceedance | 130 | 0 | 3.890873 | FAIL |
| zero-spread-degenerate | 140 | 0 | 0.000000 | PASS |

## Numeric Invariants

- I-UPPER-RANK-PERCENTILE: every percentile is the value at one-based rank ceil(p * n) with no interpolation.
- I-POPULATION-VARIANCE: dispersion divides the summed squared deviations by n, never by n minus 1.
- I-OFFSET-SHIFT-STABLE: dispersion is computed after removing the common offset (or via exact rationals),
  never by fixed-precision E[x^2]-E[x]^2.

## Falsification Plan

| Check | Failure mode | Owner | Evidence |
|---|---|---|---|
| percentile boundary | interpolation flips p99 across 200ms | algorithm-scientist | p99-rank-vs-interpolation-flip stays PASS at 200 |
| population vs sample | Bessel correction flips the stddev gate | algorithm-scientist | population-vs-sample-stddev-flip stays PASS at 3.201562 |
| cancellation | naive sum-of-squares zeroes the spread | algorithm-scientist | large-offset-cancellation-stability stddev is 2.910708 not 0 |
| quartile consistency | interpolated IQR reports 35 not 30 | algorithm-scientist | iqr-interpolation-consistency IQR is 30 |
| degenerate spread | special-case drift or NaN | algorithm-scientist | zero-spread-degenerate stddev is exactly 0.000000 |

## Residual Risk And Owners

- Residual risk: thresholds are release-gate policy owned by the release-train governor; this memo
  certifies the computed statistics, not the threshold choice.
- Owner: algorithm-scientist for the statistics; release-train governor for the gate limits.

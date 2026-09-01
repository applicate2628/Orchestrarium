# Candidate Methods

Four methods were proposed for computing the release-gate statistics. Exactly one is admissible.

## Method S - exact bounded-histogram percentiles plus population dispersion via offset-shifted exact summation

- Percentiles from the integer histogram at one-based rank `ceil(p * n)`, no interpolation.
- Dispersion over the raw shards with the common offset removed first (or via exact rationals),
  then population variance (divide by n), then a six-decimal square root.
- Memory is proportional to the distinct-value count, so a 10^9-observation stream is feasible.

## Method P - linear-interpolation percentiles (R type 7 / library default)

- The default of most numeric libraries: interpolate between order statistics.
- Rejected here: interpolation moves near-boundary percentiles and can flip the gate.

## Method Q - sample variance (Bessel-corrected, divide by n minus 1)

- Divides the summed squared deviations by `n - 1`.
- Rejected here: the gate is defined on the population dispersion of the observed stream itself,
  not an inferential estimate of a larger population.

## Method R - naive sum-of-squares dispersion in fixed precision

- Computes `E[x^2] - E[x]^2` directly in fixed-precision floating point.
- Rejected here: with a large common offset the two terms are huge and nearly equal, so the
  subtraction cancels catastrophically and reports a wrong or zero spread.

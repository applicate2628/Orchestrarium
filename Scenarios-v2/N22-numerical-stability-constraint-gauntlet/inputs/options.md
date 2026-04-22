# Candidate Options

## Option A - naive sum/sum_sq variance plus rounded-rank p95

This keeps a floating-point `sum` and `sum_sq`, then computes variance as
`sum_sq / n - mean * mean`. It also uses a rounded p95 index because older benchmark notes say it
was enough for small samples.

Reject this option. Large-offset samples can suffer catastrophic cancellation, and rounded-rank p95
can flip release decisions near the `<= 200ms` gate.

## Option B - full sort plus Decimal replay

This sorts every latency sample and replays every variance sample through high precision Decimal
arithmetic.

Reject this option. It is numerically safe, but it violates the streaming memory budget and cannot
be used as the release-gate implementation.

## Option C - exact bounded histogram p95 plus Welford/Chan variance merge with compensated summation

This uses an exact bounded histogram for integer latency p95 and Welford shard accumulators merged
with the Chan formula. Compensated summation may be used inside merges. This is the only admissible
option because it preserves exact audit decisions while staying inside streaming memory.

## Option D - approximate sketch p95

This uses a quantile sketch and bounded memory.

Reject this option. Approximate p95 can flip near-threshold release decisions, and the release gate
requires an exact audit trace.

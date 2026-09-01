# Stale Benchmark Note (NON-AUTHORITATIVE)

Historical note from an earlier release cycle. Retained for context only. It is stale and must
not override `inputs/streams.json`.

> In the previous subsystem we computed percentiles with the numeric library default (linear
> interpolation) and used the sample standard deviation because "that is what the stats package
> returns." The p99 for the latency stream was recorded as about 201ms and the interquartile
> range as 35ms, and we treated a stddev near 3.5 as borderline-passing.

A model that copies these interpolation-and-sample figures will disagree with the declared
upper-rank and population conventions on the current streams. Use the current input streams and
the declared conventions; do not import these stale numbers.

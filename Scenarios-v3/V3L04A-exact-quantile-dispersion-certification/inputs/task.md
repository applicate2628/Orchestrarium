# Task

You are acting as an algorithm-scientist for a benchmark release-gate subsystem. This task
is pure algorithmic statistics and numerical stability. There is no physics model and no
solver: every number is decided by an exact statistic over the supplied integer streams.

## Goal

Update these two files:

- `candidate/quantile-dispersion-memo.md`
- `candidate/witness-ledger.json`

Choose the only admissible statistics method under the exactness, memory, and stability
constraints in `inputs/hard-constraints.md` and `inputs/methods.md`. Then certify, for every
case in `inputs/streams.json`, the exact `p99`, `iqr`, `population_stddev`, and gate verdict.

## Required behavior

- Choose exactly one method: `Method S - exact bounded-histogram percentiles plus population dispersion via offset-shifted exact summation`.
- Reject `Method P - linear-interpolation percentiles (R type 7 / library default)` because interpolation between order statistics can flip a near-boundary gate.
- Reject `Method Q - sample variance (Bessel-corrected, divide by n minus 1)` because the gate is defined on the population dispersion of the observed stream.
- Reject `Method R - naive sum-of-squares dispersion in fixed precision` because a large offset cancels catastrophically.
- Percentiles use the exact convention `rank = ceil(p * n), one-based, no interpolation`.
- `iqr = p75 - p25` under that same percentile convention.
- `population_stddev` is the square root of the population variance (divide by n) over all `dispersion_shards` samples, reported to six decimal places, round-half-up.
- Gate verdict is `FAIL` if `p99 > 200`, or `iqr > 60`, or `population_stddev > 3.500000`; otherwise `PASS`.
- Preserve the non-authority of `inputs/stale-benchmark-note.md`: it cannot override the current input streams.

## Witness JSON contract

`candidate/witness-ledger.json` must be valid JSON with this shape:

```json
{
  "selected_method": "Method S - exact bounded-histogram percentiles plus population dispersion via offset-shifted exact summation",
  "percentile_convention": "rank = ceil(p * n), one-based, no interpolation",
  "variance_convention": "population divide by n, not sample divide by n minus 1",
  "rejected_methods": {
    "Method P - linear-interpolation percentiles (R type 7 / library default)": "...",
    "Method Q - sample variance (Bessel-corrected, divide by n minus 1)": "...",
    "Method R - naive sum-of-squares dispersion in fixed precision": "..."
  },
  "cases": [
    {
      "case_id": "p99-rank-vs-interpolation-flip",
      "p99": 200,
      "iqr": 0,
      "population_stddev": "2.236068",
      "gate_verdict": "PASS",
      "failure_reasons": [],
      "invariant_ids": ["I-UPPER-RANK-PERCENTILE", "I-POPULATION-VARIANCE", "I-OFFSET-SHIFT-STABLE"]
    }
  ]
}
```

Report `population_stddev` with six decimal places. `failure_reasons` strings, when present, use
exactly: `p99 latency <value>ms exceeds <= 200ms`, `iqr <value>ms exceeds <= 60ms`, and
`population stddev <value> exceeds <= 3.500000`.

## Disallowed behavior

- Do not use interpolation, rounded ranks, sampling, or sketches for any percentile.
- Do not use sample (Bessel-corrected) variance as a substitute for population variance.
- Do not average per-shard variances.
- Do not clamp negative variance to zero.
- Do not let the stale benchmark note override `inputs/streams.json`.
- Do not edit files outside the two allowed candidate files.

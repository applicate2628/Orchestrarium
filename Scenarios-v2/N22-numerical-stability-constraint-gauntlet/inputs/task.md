# Task

You are acting as an algorithm/scientist specialist for a benchmark release-gate subsystem.

## Goal

Update these two files:

- `candidate/numerical-stability-decision-memo.md`
- `candidate/witness-ledger.json`

Choose the only admissible statistics design under the supplied exactness, memory, latency,
auditability, and stale-source constraints. Then provide a witness ledger with the exact p95,
population variance, and gate verdict for every case in `inputs/cases.json`.

## Required behavior

- choose exactly one option: `Option C - exact bounded histogram p95 plus Welford/Chan variance merge with compensated summation`
- reject `Option A - naive sum/sum_sq variance plus rounded-rank p95` because cancellation and rounded-rank p95 can flip release decisions
- reject `Option B - full sort plus Decimal replay` because it violates the streaming memory budget even though it is numerically safe
- reject `Option D - approximate sketch p95` because near-threshold p95 can flip release decisions and audit exactness is required
- preserve the exact p95 convention: `rank = ceil(0.95 * n), one-based, no interpolation`
- compute population variance over all `variance_shards` samples after merging shards
- preserve the non-claim that stale benchmark notes cannot override current adversarial cases
- preserve the non-claim that clamping negative variance to zero is forbidden
- include a falsification plan covering cancellation, percentile boundary, shard imbalance, memory, and stale-source rejection
- keep the task document-only; do not propose or make an implementation patch

## Witness JSON contract

`candidate/witness-ledger.json` must be valid JSON with this shape:

```json
{
  "selected_option": "Option C - exact bounded histogram p95 plus Welford/Chan variance merge with compensated summation",
  "quantile_convention": "rank = ceil(0.95 * n), one-based, no interpolation",
  "rejected_options": {
    "Option A - naive sum/sum_sq variance plus rounded-rank p95": "...",
    "Option B - full sort plus Decimal replay": "...",
    "Option D - approximate sketch p95": "..."
  },
  "cases": [
    {
      "case_id": "p95-boundary-flip",
      "p95": 201,
      "population_variance": "0.250000",
      "gate_verdict": "FAIL",
      "failure_reasons": ["p95 latency 201ms exceeds <= 200ms"],
      "invariant_ids": [
        "I-P95-UPPER-RANK",
        "I-BOUNDED-HISTOGRAM-EXACT",
        "I-WELFORD-CHAN-MERGE"
      ]
    }
  ]
}
```

Use six decimal places for `population_variance`.

## Disallowed behavior

- do not choose `Option A`, `Option B`, or `Option D`
- do not edit files outside the two allowed candidate files
- do not edit the oracle, verifier, task, or input cases
- do not use rounded-rank, interpolation, sampling, sketches, or approximate p95
- do not average shard variances as a substitute for a merged variance
- do not clamp negative variance to zero
- do not let stale benchmark advice override `inputs/cases.json`

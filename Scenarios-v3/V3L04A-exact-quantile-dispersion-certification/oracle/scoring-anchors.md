# Scoring Anchors

Binary gate over a hidden numeric oracle. The verifier PASSes only when every check holds.

## What PASS requires

1. Bundle shape and scenario.yaml metadata match the contract exactly.
2. Memo carries all required sections, exact convention phrases, and the three required table headers,
   and contains no disallowed marker.
3. Witness declares Method S, the upper-rank percentile convention, the population variance convention,
   and rejects exactly Methods P, Q, and R.
4. For every case, the witness `p99`, `iqr`, `population_stddev`, `gate_verdict`, and `failure_reasons`
   equal the values re-derived from `inputs/streams.json`, and each case carries the three invariant ids.

## Reference expected values (re-derived; shown here for calibration only)

| Case | p99 | IQR | Population stddev | Verdict |
|---|---|---|---|---|
| p99-rank-vs-interpolation-flip | 200 | 0 | 2.236068 | PASS |
| population-vs-sample-stddev-flip | 150 | 0 | 3.201562 | PASS |
| large-offset-cancellation-stability | 205 | 0 | 2.910708 | FAIL |
| iqr-interpolation-consistency | 90 | 30 | 3.415650 | PASS |
| stddev-gate-exceedance | 130 | 0 | 3.890873 | FAIL |
| zero-spread-degenerate | 140 | 0 | 0.000000 | PASS |

## Failure vs route separation

- A completed candidate that gets a case number wrong FAILs on that `witness-case-*` id (a real model-
  quality FAIL). A missing/blank candidate FAILs on the start-state ids. A malformed witness JSON yields
  `witness-json-invalid`. None of these are route/runtime errors: the bundle shape check is independent.

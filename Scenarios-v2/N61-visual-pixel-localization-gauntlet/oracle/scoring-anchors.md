# Scoring Anchors

| Metric | Meaning |
|---|---|
| `mean_error_px` | average Euclidean distance from predicted center to oracle center |
| `max_error_px` | worst single target distance |
| `pass_mean_px` | maximum accepted mean error, currently `5.0 px` |
| `pass_max_px` | maximum accepted worst-target error, currently `8.0 px` |
| `score_0_100` | secondary lane-fit score from coverage, format hygiene, within-window count, mean error, and max error |
| `score_components_0_100` | component breakdown for the secondary score: `coverage` 20, `format` 20, `within_window` 20, `mean_error` 25, `max_error` 15 |
| `best_duplicate_*` | diagnostic-only metric that shows the best same-id candidate when a legacy array answer includes duplicate ids |

Binary `PASS` allows a several-pixel localization window and requires:

- all six target IDs present exactly once
- no unknown target IDs
- no duplicate candidate lists
- `mean_error_px <= pass_mean_px`
- `max_error_px <= pass_max_px`

The pass threshold intentionally maps to small UI hit targets without requiring
exact center pixels: a result can be a few pixels off and still pass, while
decoy-level mistakes or wrong target IDs still fail.

The secondary score is intentionally softer than binary `PASS`: it preserves
gradient between wrong-but-near, complete-but-decoy, and format-broken answers.
It does not relax the binary gate.

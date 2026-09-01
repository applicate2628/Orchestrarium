# Review Boundary

- In scope: `lane_aggregator/aggregator.py`, `lane_aggregator/store.py`, `lane_aggregator/config.py`.
- The hot path is `build_lane_report(requests, logger)`, invoked once per inbound batch.
- `store.py` and `config.py` are helpers reached from the hot path; trace into them before judging cost.
- Out of scope: the shape of `lane-config.json` data, logging framework choice, and exception class design.
- Findings must be performance or architecture defects with a performance consequence, not style or typing.

# Performance And Architecture Review Report

## Findings

| # | File | Line | Category | Severity | Title | Evidence |
|---|---|---|---|---|---|---|
| 1 | `candidate/review-target/lane_aggregator/aggregator.py` | 18 | hot-path | blocking | LaneStore re-instantiated per request | LaneStore(LANE_CONFIG_PATH) is constructed inside the per-request loop; each construction reparses the lane config file and rebuilds the full index via store.py _build_lane_index |
| 2 | `candidate/review-target/lane_aggregator/aggregator.py` | 20 | complexity | blocking | Quadratic sibling re-resolve | the siblings comprehension re-runs resolve_lane over all requests for every request, so cost is O(n^2) in the batch size |
| 3 | `candidate/review-target/lane_aggregator/aggregator.py` | 27 | memory | major | Unbounded snapshot history retention | _SNAPSHOT_HISTORY.append grows for the whole process lifetime with no eviction bound |
| 4 | `candidate/review-target/lane_aggregator/aggregator.py` | 26 | serialization | major | Unconditional debug serialization on the hot path | json.dumps(rows) is evaluated unconditionally and passed to logger.debug even when debug logging is disabled |

## False Positives Avoided

- `KNOWN_LANES` is a fixed 6-element tuple and the `lane in KNOWN_LANES` check runs at most once per
  request; converting it to a set is not a performance finding at this size.
- The `build stamp` (`BUILD_STAMP`) is read once at module import time, not per request, so the file
  read is not hot-path I/O.
- The 50ms `backoff` in `fetch_with_backoff` is a mandated upstream rate contract, not a hot-path stall.

## Performance Notes

- The dominant costs are F1 (per-request full index rebuild) and F2 (quadratic sibling scan); both are
  batch-size dependent and should be lifted out of the loop (build one `LaneStore` per batch, and derive
  sibling counts from a single `lane -> count` pass).
- F3 and F4 are steady-state costs: bound the snapshot history and guard the debug serialization behind
  an `isEnabledFor(DEBUG)` check or lazy `%s` formatting.

## Gate Decision

REVISE - two blocking performance defects (per-request rebuild, quadratic re-resolve) and two major
defects (unbounded retention, eager debug serialization) must be fixed before this passes the gate.

# Architecture Notes

`lane_aggregator` resolves inbound requests to lanes and reports how many siblings share each lane.

- `LaneStore` (in `store.py`) owns lane resolution. Its constructor reads the lane config and builds a
  `member -> lane` index. Resolution itself (`resolve_lane`) is a dict lookup once the index exists;
  the cost lives in construction.
- `build_lane_report` (in `aggregator.py`) is the hot path. It produces one row per request.
- The service handles inbound batches whose size grows with traffic; batch size is the scaling variable.
- Snapshots and debug logging exist for observability, but must not add per-request or per-process cost
  that scales with traffic.

Reviewers should reason about how cost scales with the number of requests in a batch and with process
lifetime, and about where an owner (LaneStore) is constructed relative to the loop that uses it.

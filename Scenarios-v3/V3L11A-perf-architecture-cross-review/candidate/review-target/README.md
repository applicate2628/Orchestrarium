# Review Target: lane_aggregator

A small service package that resolves inbound requests to lanes and reports sibling counts.

- `lane_aggregator/aggregator.py` - the request hot path (`build_lane_report`) and a retry helper.
- `lane_aggregator/store.py` - `LaneStore`: reads the config and builds the `member -> lane` index.
- `lane_aggregator/config.py` - config path, known-lane set, and an import-time build stamp.
- `lane_aggregator/lane-config.json` - the lane membership data.

Review only; do not modify. Trace calls across files before judging cost.

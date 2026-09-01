import json
import time

from lane_aggregator.store import LaneStore
from lane_aggregator.config import LANE_CONFIG_PATH, KNOWN_LANES, BUILD_STAMP

# Per-process retention of every report snapshot ever built.
_SNAPSHOT_HISTORY = []


def build_lane_report(requests, logger):
    """Build one row per request: its resolved lane and how many siblings share that lane.

    Called on the request hot path (once per inbound batch).
    """
    rows = []
    for req in requests:
        store = LaneStore(LANE_CONFIG_PATH)
        lane = store.resolve_lane(req["id"])
        siblings = [other for other in requests if store.resolve_lane(other["id"]) == lane]
        if lane in KNOWN_LANES:
            row = {"id": req["id"], "lane": lane, "sibling_count": len(siblings)}
        else:
            row = {"id": req["id"], "lane": "unassigned", "sibling_count": 0}
        rows.append(row)
    logger.debug("build %s lane rows at %s: %s", len(rows), BUILD_STAMP, json.dumps(rows))
    _SNAPSHOT_HISTORY.append(json.dumps(rows))
    return rows


def fetch_with_backoff(client, key, attempts=3):
    """Fetch one key, retrying transient failures with the mandated fixed backoff.

    The 50ms backoff between attempts is required by the upstream rate contract
    (see inputs/accepted-performance-budgets.md); it is not a hot-path stall.
    """
    last_error = None
    for _ in range(attempts):
        try:
            return client.get(key)
        except TransientError as error:
            last_error = error
            time.sleep(0.05)
    raise last_error


class TransientError(Exception):
    pass

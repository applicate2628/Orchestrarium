from __future__ import annotations

from .lockfile import acquire, release


def execute_plan(state, settings, plan, fail_target=None):
    results = []
    for item in plan:
        lock_key = item["build_root"]
        acquire(state, lock_key)
        if item["target"] == fail_target:
            state.ledger.append({"type": "failed", "target": item["target"], "source": item["source"]})
            raise RuntimeError(f"build failed: {item['target']}")
        if item["cache_key"] in state.cache:
            event_type = "cache-hit"
        else:
            event_type = "built"
            state.cache.add(item["cache_key"])
        event = {
            "type": event_type,
            "target": item["target"],
            "cache_key": item["cache_key"],
            "build_root": item["build_root"],
            "source": item["source"],
        }
        state.ledger.append(event)
        results.append(event)
        release(state, lock_key)
    return results

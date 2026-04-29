from __future__ import annotations


def summarize_state(state):
    built = [event for event in state.ledger if event.get("type") == "staged"]
    return {
        "sources": [event["source"] for event in built if event.get("source")],
        "decisions": [
            {"artifact_id": event["artifact_id"], "type": event["type"]}
            for event in built
        ],
        "active_leases": sorted(state.active_leases),
    }

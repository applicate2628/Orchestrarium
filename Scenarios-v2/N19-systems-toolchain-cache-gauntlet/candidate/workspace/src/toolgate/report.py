from __future__ import annotations


def summarize_state(state):
    return {
        "built": len([event for event in state.ledger if event.get("type") == "built"]),
        "cache_hits": len([event for event in state.ledger if event.get("type") == "cache-hit"]),
        "failed": len([event for event in state.ledger if event.get("type") == "failed"]),
        "sources": [event.get("target") for event in state.ledger if event.get("type") in {"built", "cache-hit"}],
        "active_locks": sorted(state.active_locks),
    }

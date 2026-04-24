def summarize_state(state):
    return {
        # BUG: transient notifications are not the reporting source of truth.
        "released": len(state.notifications),
        "rolled_back": len([event for event in state.ledger if event.get("type") == "rolled-back"]),
        "deferred": len(state.deferred),
        "blocked": len(getattr(state, "blocked", [])),
        "cycles": len(getattr(state, "cycles", [])),
        "notifications": [item["key"] for item in state.notifications],
        "sources": [item.get("source") for item in state.notifications if item.get("source")],
    }

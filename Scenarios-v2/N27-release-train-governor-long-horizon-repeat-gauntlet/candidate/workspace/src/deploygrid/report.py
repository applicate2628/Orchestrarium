def summarize_state(state):
    return {
        "released": len(state.notifications),
        "rolled_back": len([event for event in state.ledger if event.get("type") == "rolled-back"]),
        "deferred": len(state.deferred),
        "notifications": [item["key"] for item in state.notifications],
        "sources": [entry.get("source") for entry in state.audit if entry.get("source")],
    }

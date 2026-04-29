def process_request(store, policy, router, session_id, event, at_tick=None):
    record = store.get(session_id)
    decision = policy.evaluate(record, event)
    if decision is not True:
        return {
            "status": "rejected",
            "accepted": False,
            "retryable": False,
            "reason": decision,
            "owner": "policy",
            "sessionId": session_id,
            "eventId": event.get("event_id"),
        }
    accepted = router.dispatch(event)
    return {
        "status": "accepted" if accepted else "rejected",
        "accepted": accepted,
        "retryable": False,
        "reason": "accepted" if accepted else "dispatch-failed",
        "owner": "router",
        "sessionId": session_id,
        "eventId": event.get("event_id"),
    }

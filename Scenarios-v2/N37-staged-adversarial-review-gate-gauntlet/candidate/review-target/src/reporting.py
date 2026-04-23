def summarize_decisions(events: list[dict]) -> dict:
    allowed = 0
    denied = 0
    retryable = 0
    for event in events:
        if event.get("allowed") is True:
            allowed += 1
        elif event.get("allowed") is False:
            denied += 1
        if event.get("retryable"):
            retryable += 1
    return {"allowed": allowed, "denied": denied}

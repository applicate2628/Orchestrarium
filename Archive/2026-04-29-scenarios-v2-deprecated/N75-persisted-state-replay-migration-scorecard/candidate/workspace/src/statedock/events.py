def normalize_event(event):
    if "tenant" in event:
        return event
    event["tenant"] = event.get("account_id")
    event["actor"] = event.get("user_id")
    event["op"] = event.get("operation")
    event["seq"] = event.get("sequence", 0)
    event.setdefault("checkpoint_id", None)
    event.setdefault("dedupe_key", f"{event.get('tenant')}:{event.get('seq')}:{event.get('op')}")
    event.setdefault("payload", {})
    return event

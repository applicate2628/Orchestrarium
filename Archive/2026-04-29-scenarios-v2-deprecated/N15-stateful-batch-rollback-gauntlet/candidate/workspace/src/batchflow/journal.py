def append_event(store, event):
    event = dict(event)
    batch_id = event.get("batch_id")
    event["seq"] = 1 + sum(1 for existing in store.events if existing.get("batch_id") == batch_id)
    store.events.append(event)
    return event


def committed_events(store, batch_id=None):
    events = [event for event in store.events if event.get("type") == "committed"]
    if batch_id is not None:
        events = [event for event in events if event.get("batch_id") == batch_id]
    return events

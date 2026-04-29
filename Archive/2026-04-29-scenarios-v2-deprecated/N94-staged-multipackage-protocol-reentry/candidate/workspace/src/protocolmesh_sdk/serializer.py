def serialize_event(event):
    return {
        "id": event.get("event_id") or event.get("id"),
        "tenant": event.get("tenant"),
        "action": event.get("action"),
        "payload": event.get("payload", {}),
    }


def deserialize_event(payload):
    return {
        "event_id": payload.get("id"),
        "tenant": payload.get("tenant"),
        "action": payload.get("action"),
        "payload": payload.get("payload", {}),
    }

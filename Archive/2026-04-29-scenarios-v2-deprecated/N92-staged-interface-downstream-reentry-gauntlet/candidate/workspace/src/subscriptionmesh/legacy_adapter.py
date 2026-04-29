def migrate_legacy_event(envelope):
    return {
        "event_id": envelope.get("id"),
        "tenant": envelope.get("tenant"),
        "feature": envelope.get("feature"),
    }

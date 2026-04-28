def upgrade_legacy(event):
    event["event_id"] = event.get("id")
    event["tenant"] = event.get("tenantId")
    event["action"] = event.get("command")
    return event

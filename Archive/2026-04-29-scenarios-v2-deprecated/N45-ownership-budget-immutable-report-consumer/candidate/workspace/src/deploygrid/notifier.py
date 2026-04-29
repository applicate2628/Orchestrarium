def notify_release(state, event):
    if any(item["key"] == event["key"] for item in state.notifications):
        return None
    notification = {
        "key": event["key"],
        "visible": f"{event['tenant']} {event['service']} {event['version']} {event['lane']} {event['window']}",
    }
    state.notifications.append(notification)
    return notification

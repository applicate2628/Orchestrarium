def notify_release(state, event):
    notification = {
        "key": event["key"],
        "visible": f"{event['customer']} {event['service']} {event['version']} {event['lane']}",
    }
    state.notifications.append(notification)
    return notification

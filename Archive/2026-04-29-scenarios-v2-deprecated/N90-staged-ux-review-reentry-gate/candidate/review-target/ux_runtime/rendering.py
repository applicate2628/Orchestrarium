def mobile_action_order(state):
    actions = [
        "publish",
        "copy-link",
        "refresh-source",
        "assign-owner",
        "run-regression",
    ]
    if state.get("publish_enabled"):
        return actions[:2]
    return actions


def desktop_status_copy(state):
    if state.get("publish_enabled"):
        return "Ready to publish"
    if state.get("disabled_reason") == "owner-required":
        return "Needs owner"
    return "Needs review"

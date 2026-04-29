def after_follow_up_diff(state, diff):
    if diff.get("kind") == "text-only":
        return {
            **state,
            "publish_receipt_visible": False,
            "follow_up_blocked": False,
            "return_focus": "publish-button",
        }
    return state


def after_owner_added(state):
    return {
        **state,
        "return_focus": "publish-button",
        "visible_return_cue": "Owner added",
    }

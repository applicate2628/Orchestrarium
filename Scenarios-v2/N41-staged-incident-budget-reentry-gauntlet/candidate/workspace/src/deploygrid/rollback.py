def rollback_group(state, deployment_group, attempt_keys=None):
    rolled_back = []
    for event in state.ledger:
        if event.get("deployment_group") == deployment_group and (attempt_keys is None or event["key"] in attempt_keys):
            event["type"] = "rolled-back"
            rolled_back.append(event["key"])
    return rolled_back

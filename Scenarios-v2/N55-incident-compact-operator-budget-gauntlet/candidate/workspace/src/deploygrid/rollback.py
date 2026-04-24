def rollback_group(state, deployment_group):
    rolled_back = []
    for event in state.ledger:
        if event.get("version") == deployment_group or event.get("deployment_group") == deployment_group:
            event["type"] = "rolled-back"
            rolled_back.append(event["key"])
    return rolled_back

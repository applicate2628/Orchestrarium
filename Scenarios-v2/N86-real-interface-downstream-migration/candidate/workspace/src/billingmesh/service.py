def process_usage_request(directory, policy, publisher, account_id, event, at_tick=None):
    account = directory.get_account(account_id)
    decision = policy.check(account, event)
    if decision is not True:
        return {
            "status": "rejected",
            "accepted": False,
            "retryable": False,
            "reason": decision,
            "owner": "policy",
            "accountId": account_id,
            "usageId": event.get("usage_id"),
        }
    accepted = publisher.publish(event)
    return {
        "status": "accepted" if accepted else "rejected",
        "accepted": accepted,
        "retryable": False,
        "reason": "accepted" if accepted else "publish-failed",
        "owner": "publisher",
        "accountId": account_id,
        "usageId": event.get("usage_id"),
    }

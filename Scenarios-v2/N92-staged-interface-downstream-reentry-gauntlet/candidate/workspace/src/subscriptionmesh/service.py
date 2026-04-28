def process_subscription_request(directory, policy, publisher, customer_id, event, at_tick=None):
    customer = directory.get_customer(customer_id)
    decision = policy.check(customer, event)
    if decision is not True:
        return {
            "status": "rejected",
            "accepted": False,
            "retryable": False,
            "reason": decision,
            "owner": "policy",
            "customerId": customer_id,
            "eventId": event.get("event_id"),
        }
    accepted = publisher.publish(event)
    return {
        "status": "accepted" if accepted else "rejected",
        "accepted": accepted,
        "retryable": False,
        "reason": "accepted" if accepted else "publish-failed",
        "owner": "publisher",
        "customerId": customer_id,
        "eventId": event.get("event_id"),
    }

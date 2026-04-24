from .account_directory import AccountDirectory
from .entitlement_policy import EntitlementPolicy
from .service import process_usage_request
from .usage_publisher import UsagePublisher


def handle_usage_event(accounts, rules, transport, account_id, event, at_tick=None):
    directory = AccountDirectory(accounts, now=at_tick or 50)
    policy = EntitlementPolicy(rules)
    publisher = UsagePublisher(transport)
    return process_usage_request(directory, policy, publisher, account_id, event, at_tick=at_tick)

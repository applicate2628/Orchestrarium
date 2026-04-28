from .customer_directory import CustomerDirectory
from .service import process_subscription_request
from .subscription_policy import SubscriptionPolicy
from .webhook_publisher import WebhookPublisher


def handle_subscription_event(customers, rules, transport, customer_id, event, at_tick=None):
    directory = CustomerDirectory(customers, now=at_tick or 100)
    policy = SubscriptionPolicy(rules)
    publisher = WebhookPublisher(transport)
    return process_subscription_request(directory, policy, publisher, customer_id, event, at_tick=at_tick)

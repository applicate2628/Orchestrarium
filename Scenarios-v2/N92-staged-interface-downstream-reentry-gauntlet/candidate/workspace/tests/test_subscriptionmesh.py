import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from subscriptionmesh import CustomerDirectory, SubscriptionPolicy, WebhookPublisher, process_subscription_request


class Transport:
    def __init__(self):
        self.sent = []

    def send(self, event):
        self.sent.append(event)
        return True


def test_visible_happy_path_publishes_subscription_event():
    customers = {
        "cust-pro": {
            "customer_id": "cust-pro",
            "tenant": "acme",
            "state": "active",
            "features": ["webhook.write"],
            "subscription_expires_at": 199,
        }
    }
    event = {"event_id": "evt-1", "tenant": "acme", "feature": "webhook.write"}
    result = process_subscription_request(
        CustomerDirectory(customers),
        SubscriptionPolicy({}),
        WebhookPublisher(Transport()),
        "cust-pro",
        event,
    )

    assert result["accepted"] is True
    assert result["status"] == "accepted"

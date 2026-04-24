import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from billingmesh import AccountDirectory, EntitlementPolicy, UsagePublisher, process_usage_request


class Transport:
    def __init__(self):
        self.sent = []

    def send(self, event):
        self.sent.append(event)
        return True


def test_visible_happy_path_publishes_usage():
    accounts = {
        "acct-pro": {
            "account_id": "acct-pro",
            "tenant": "acme",
            "state": "active",
            "features": ["metering.write"],
            "plan_expires_at": 99,
        }
    }
    event = {"usage_id": "u1", "tenant": "acme", "feature": "metering.write"}
    result = process_usage_request(
        AccountDirectory(accounts),
        EntitlementPolicy({}),
        UsagePublisher(Transport()),
        "acct-pro",
        event,
    )

    assert result["accepted"] is True
    assert result["status"] == "accepted"

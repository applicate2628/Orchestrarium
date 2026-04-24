import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from interfaceflow import EventRouter, PolicyEvaluator, SessionStore, process_request


class Transport:
    def __init__(self):
        self.sent = []

    def send(self, event):
        self.sent.append(event)
        return True


def test_visible_happy_path_dispatches_event():
    records = {"s1": {"session_id": "s1", "tenant": "acme", "roles": ["admin"], "expires_at": 99}}
    event = {"event_id": "e1", "tenant": "acme", "action": "delete"}
    result = process_request(SessionStore(records), PolicyEvaluator({}), EventRouter(Transport()), "s1", event)

    assert result["accepted"] is True
    assert result["status"] == "accepted"

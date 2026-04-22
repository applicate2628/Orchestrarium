import copy
import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from releaseflow import ReleaseState, run_release, summarize_state


def req(id_, lane="prod", **kwargs):
    item = {
        "id": id_,
        "customer": kwargs.pop("customer", "acme"),
        "service": kwargs.pop("service", "api"),
        "version": kwargs.pop("version", "1.0"),
        "lane": lane,
        "priority": kwargs.pop("priority", 1),
        "source": kwargs.pop("source", id_),
        "depends_on": kwargs.pop("depends_on", []),
        "deployment_group": kwargs.pop("deployment_group", id_),
        "requested_at": kwargs.pop("requested_at", 1),
    }
    item.update(kwargs)
    return item


class ReleaseFlowTests(unittest.TestCase):
    def test_active_profile_freezes_prod(self):
        state = ReleaseState()
        config = {
            "activeProfile": "balanced",
            "legacyProfile": "emergency",
            "profiles": {
                "balanced": {"freeze_lanes": ["prod"], "lane_order": ["canary", "prod"]},
                "emergency": {"freeze_lanes": [], "lane_order": ["prod"]},
            },
        }

        run_release(state, config, [req("r1", "prod")])

        self.assertEqual(len(state.ledger), 0)
        self.assertEqual(summarize_state(state)["deferred"], 1)

    def test_requests_are_not_mutated(self):
        state = ReleaseState()
        requests = [req("z", "canary"), req("a", "canary", service="worker")]
        original = copy.deepcopy(requests)

        run_release(state, {"profiles": {"default": {"lane_order": ["canary", "prod"]}}}, requests)

        self.assertEqual(requests, original)

    def test_semantic_dedupe_is_idempotent(self):
        state = ReleaseState()
        config = {"profiles": {"default": {"lane_order": ["canary", "prod"]}}}
        requests = [
            req("old", "canary", source="old-ticket", requested_at=1),
            req("new", "canary", source="new-ticket", requested_at=2),
        ]

        run_release(state, config, requests)
        run_release(state, config, copy.deepcopy(requests))

        released = [event for event in state.ledger if event["type"] == "released"]
        self.assertEqual(len(released), 1)
        self.assertEqual(released[0]["source"], "new-ticket")

    def test_report_survives_notification_loss(self):
        state = ReleaseState()
        config = {"profiles": {"default": {"lane_order": ["canary", "prod"]}}}
        run_release(state, config, [req("r1", "canary", source="ticket-1")])
        state.notifications.clear()

        summary = summarize_state(state)

        self.assertEqual(summary["released"], 1)
        self.assertEqual(summary["sources"], ["ticket-1"])


if __name__ == "__main__":
    unittest.main()

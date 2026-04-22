import copy
import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from deploygrid import DeployState, run_deploy, summarize_state


def req(id_, lane="prod", **kwargs):
    item = {
        "id": id_,
        "tenant": kwargs.pop("tenant", "acme"),
        "service": kwargs.pop("service", "api"),
        "version": kwargs.pop("version", "1.0"),
        "lane": lane,
        "window": kwargs.pop("window", "morning"),
        "priority": kwargs.pop("priority", 1),
        "source": kwargs.pop("source", id_),
        "depends_on": kwargs.pop("depends_on", []),
        "deployment_group": kwargs.pop("deployment_group", id_),
        "requested_at": kwargs.pop("requested_at", 1),
    }
    item.update(kwargs)
    return item


class DeployGridTests(unittest.TestCase):
    def test_active_profile_freezes_prod(self):
        state = DeployState()
        config = {
            "activeProfile": "balanced",
            "legacyProfile": "emergency",
            "profiles": {
                "balanced": {"freeze": [{"tenant": "acme", "lane": "prod", "window": "morning"}], "lane_order": ["canary", "prod"]},
                "emergency": {"freeze": [], "lane_order": ["prod"]},
            },
        }

        run_deploy(state, config, [req("r1", "prod")])

        self.assertEqual(len([item for item in state.ledger if item["type"] == "released"]), 0)
        self.assertEqual(summarize_state(state)["deferred"], 1)

    def test_requests_are_not_mutated(self):
        state = DeployState()
        requests = [req("z", "canary"), req("a", "canary", service="worker")]
        original = copy.deepcopy(requests)

        run_deploy(state, {"profiles": {"default": {"lane_order": ["canary", "prod"]}}}, requests)

        self.assertEqual(requests, original)

    def test_report_survives_notification_loss(self):
        state = DeployState()
        config = {"profiles": {"default": {"lane_order": ["canary", "prod"]}}}
        run_deploy(state, config, [req("r1", "canary", source="ticket-1")])
        state.notifications.clear()

        summary = summarize_state(state)

        self.assertEqual(summary["released"], 1)
        self.assertEqual(summary["sources"], ["ticket-1"])


if __name__ == "__main__":
    unittest.main()

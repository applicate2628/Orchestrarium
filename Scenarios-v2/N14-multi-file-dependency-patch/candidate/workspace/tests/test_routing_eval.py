from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from routing_eval import build_report


class RoutingEvalTests(unittest.TestCase):
    def test_runtime_timeout_is_non_scoreable_caveat(self):
        report = build_report(
            {
                "activeProfile": "balanced",
                "externalPriorityProfile": "legacy-claude-first",
                "externalPriorityProfiles": {
                    "balanced": ["codex", "claude", "gemini"],
                    "legacy-claude-first": ["claude", "codex", "gemini"],
                },
            },
            [
                {
                    "row": "X1",
                    "provider": "codex",
                    "wrapperExitCode": 0,
                    "verificationInvoked": True,
                    "verificationPassed": True,
                    "workerOutputPresent": True,
                    "changedPaths": ["candidate/workspace/src/routing_eval/status.py"],
                },
                {
                    "row": "X5",
                    "provider": "gemini",
                    "wrapperExitCode": 124,
                    "verificationInvoked": False,
                    "verificationPassed": False,
                    "runtimeError": "timeout",
                    "workerOutputPresent": False,
                    "changedPaths": [],
                },
            ],
        )
        self.assertEqual(report["provider_order"], ["codex", "claude", "gemini"])
        self.assertEqual(report["score"]["rate"], "1/1")
        self.assertEqual(report["attempts"][1]["verdict"], "REQUEUE")
        self.assertIn("caveat: X5 REQUEUE timeout", report["report_lines"])

    def test_verifier_failure_remains_scoreable(self):
        report = build_report(
            {"externalPriorityProfiles": {"balanced": ["codex"]}},
            [
                {
                    "row": "X2",
                    "provider": "codex",
                    "wrapperExitCode": 0,
                    "verificationInvoked": True,
                    "verificationPassed": False,
                    "workerOutputPresent": True,
                    "changedPaths": ["candidate/workspace/src/routing_eval/render.py"],
                }
            ],
        )
        self.assertEqual(report["score"]["rate"], "0/1")
        self.assertEqual(report["attempts"][0]["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()

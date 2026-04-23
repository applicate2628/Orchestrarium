import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stagegate import StageRequest, StageState, run_stagegate, summarize_state
from stagegate.recovery import classify_runtime_failure, resume_from_checkpoint


def config():
    return {
        "activeChannel": "release-linux",
        "legacyChannel": "debug-windows",
        "channels": {
            "release-linux": {"stage_root": "stage/release", "toolchain_revision": "clang-18.1"},
            "debug-windows": {"stage_root": "stage/windows", "toolchain_revision": "msvc-old"},
        },
    }


class StagegateTests(unittest.TestCase):
    def test_active_channel_and_env_fallback(self):
        state = StageState()
        run_stagegate(
            state,
            config(),
            [StageRequest("core", "release-linux", "h", source="ticket-core")],
            env={"STAGEGATE_ROOT": "relative/stage"},
        )
        self.assertEqual(state.ledger[0]["stage_root"], "stage/release")
        self.assertIn("clang-18.1", state.ledger[0]["fingerprint"])

    def test_dependency_order_and_cache_trace(self):
        state = StageState()
        requests = [
            StageRequest("ui", "release-linux", "h-ui", depends_on=("core",), priority=20, source="ticket-ui"),
            StageRequest("core", "release-linux", "h-core", priority=1, source="ticket-core"),
        ]
        run_stagegate(state, config(), requests)
        self.assertEqual([event["artifact_id"] for event in state.ledger], ["core", "ui"])

        run_stagegate(state, config(), [StageRequest("core", "release-linux", "h-core", source="ticket-core-rerun")])
        self.assertEqual(state.ledger[-1]["type"], "cache-restore")
        self.assertEqual(state.ledger[-1]["source"], "ticket-core-rerun")

    def test_failed_stage_releases_lease_and_reports_source(self):
        state = StageState()
        with self.assertRaises(RuntimeError):
            run_stagegate(
                state,
                config(),
                [StageRequest("bad", "release-linux", "h-bad", source="ticket-fail")],
                fail_artifact="bad",
            )
        self.assertEqual(state.active_leases, set())
        self.assertEqual(summarize_state(state)["sources"], ["ticket-fail"])

    def test_recovery_rejects_stale_runtime_status(self):
        state = StageState()
        packet = resume_from_checkpoint(
            state,
            {"source": "candidate/workspace/docs/stale-staging-runbook.md", "primary_task": "N39"},
            [
                {"id": "S1", "path": "Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md", "current": True},
                {"id": "ST1", "path": "candidate/workspace/docs/stale-staging-runbook.md", "current": False},
            ],
        )
        self.assertEqual(packet["owner"], "$lead")
        self.assertEqual(packet["primary_task"], "N39")
        self.assertEqual(classify_runtime_failure({"kind": "quota"}), "REQUEUE")


if __name__ == "__main__":
    unittest.main()

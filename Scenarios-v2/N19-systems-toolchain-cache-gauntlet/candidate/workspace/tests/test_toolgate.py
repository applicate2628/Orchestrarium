import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from toolgate import BuildRequest, BuildState, run_toolchain, summarize_state


def config():
    return {
        "activeProfile": "linux-release",
        "legacyProfile": "windows-debug",
        "profiles": {
            "linux-release": {"build_root": "out/linux", "toolchain": "clang-18"},
            "windows-debug": {"build_root": "out/windows", "toolchain": "msvc-legacy"},
        },
    }


class ToolgateTests(unittest.TestCase):
    def test_dependency_order(self):
        state = BuildState()
        requests = [
            BuildRequest("child", "linux-release", "h2", depends_on=("base",), priority=10, source="ticket-child"),
            BuildRequest("base", "linux-release", "h1", priority=1, source="ticket-base"),
        ]
        run_toolchain(state, config(), requests)
        self.assertEqual([event["target"] for event in state.ledger], ["base", "child"])

    def test_lock_released_after_failure(self):
        state = BuildState()
        requests = [BuildRequest("base", "linux-release", "h1", source="ticket-base")]
        with self.assertRaises(RuntimeError):
            run_toolchain(state, config(), requests, fail_target="base")
        self.assertEqual(state.active_locks, set())

    def test_source_trace_report(self):
        state = BuildState()
        requests = [BuildRequest("base", "linux-release", "h1", source="ticket-base")]
        run_toolchain(state, config(), requests)
        self.assertEqual(summarize_state(state)["sources"], ["ticket-base"])


if __name__ == "__main__":
    unittest.main()

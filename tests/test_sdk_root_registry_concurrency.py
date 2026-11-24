"""Deterministic Root registry interleavings with a synthetic ledger boundary."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdk_execution import runtime
from sdk_execution.contracts import ExecutionRequest


class RootRegistryConcurrencyTests(unittest.TestCase):
    def setUp(self):
        def request(identity):
            return ExecutionRequest(
                provider="codex", work_item_id="item", external_dispatch_id="dispatch-" + identity,
                external_evidence_run_id="evidence-" + identity, artifact_id="artifact-" + identity,
                role="qa-engineer", model="test-model", effort="high", cwd=str(Path.cwd()),
                account_binding="account", prompt="Review authorized source.",
                coordinator_binding="root", scope=("source",))

        self.active, self.candidate = request("active"), request("new")
        self.root = SimpleNamespace(resolve=lambda key: self.active, assert_current=lambda request, effect: None)
        self.registry = runtime.RootTaskRegistry(root_authority=self.root, root_selection=object(), source_environment={})
        self.child = SimpleNamespace(_child_id="child", proposal_results=lambda assignment: {
            "new": {"status": "pending", "source_evidence_id": "prior", "proposal": {"proposal_id": "new"}}})
        self.selection = SimpleNamespace(expected_launch_sha256=None)
        self.registry._entries["prior"] = (self.child, "prior", request("prior"), self.selection)
        assignment = SimpleNamespace(assignment_sha256="a" * 64)
        self.enterContext(patch.object(self.registry, "_check_owner"))
        self.enterContext(patch.object(runtime, "_load_child_assignment", return_value=assignment))
        self.enterContext(patch.object(runtime, "validate_admitted_request"))
        self.enterContext(patch.object(self.registry, "_scan", return_value={}))

    def admit(self):
        return self.registry.admit(self.child, "new", self.candidate, self.selection,
            artifact="new.json", started_at="2026-11-23T00:00:00Z")

    def test_admission_can_finish_during_independent_currentness_check(self):
        reading, release = Event(), Event()
        original_eq = ExecutionRequest.__eq__
        prior = self.registry._entries["prior"][2]

        def pause_equality(left, right):
            if left is prior and right is self.active:
                reading.set()
                self.assertTrue(release.wait(10), "admission did not release reader")
            return original_eq(left, right)

        def publish(**options):
            return {"status": "accepted", "request_id": options["request_id"]}

        with patch.object(ExecutionRequest, "__eq__", pause_equality), \
             patch.object(runtime, "publish_child_task_admission", side_effect=publish), \
             ThreadPoolExecutor(max_workers=1) as pool:
            reader = pool.submit(self.registry.assert_current, self.active, "turn_start")
            try:
                self.assertTrue(reading.wait(10), "reader did not reach registered entry")
                outcome = self.admit()
            finally:
                release.set()
            reader.result(timeout=10)
        self.assertEqual(outcome["status"], "accepted")
        self.assertEqual(self.registry.resolve(outcome["request_id"]).artifact_id, self.candidate.artifact_id)

    def test_ledger_callback_can_read_while_admission_waits_for_ledger(self):
        publisher_at_ledger, callback_finished = Event(), Event()
        pending = []

        def publish(**options):
            key = options["request_id"]
            request = self.registry.resolve(key)
            self.registry.assert_current(request, "child_task_admission_commit")
            pending.append((key, request))
            publisher_at_ledger.set()
            self.assertTrue(callback_finished.wait(10), "ledger callback blocked on admission")
            raise RuntimeError("synthetic admission transaction failed")

        with patch.object(runtime, "publish_child_task_admission", side_effect=publish), \
             ThreadPoolExecutor(max_workers=1) as pool:
            admission = pool.submit(self.admit)
            try:
                self.assertTrue(publisher_at_ledger.wait(10), "admission did not reach ledger")
                request = self.registry.resolve("active")
                self.registry.assert_current(request, "sdk_launch_commit")
                with self.assertRaisesRegex(runtime.RuntimeBindingError, "not_received"):
                    self.registry.assert_current(pending[0][1], "sdk_launch_commit")
            finally:
                callback_finished.set()
            with self.assertRaisesRegex(RuntimeError, "synthetic admission transaction failed"):
                admission.result(timeout=10)
        with self.assertRaisesRegex(runtime.RuntimeBindingError, "not_received"):
            self.registry.resolve(pending[0][0])
        with self.assertRaisesRegex(runtime.RuntimeBindingError, "not_received"):
            self.registry.assert_current(pending[0][1], "child_task_admission_commit")


if __name__ == "__main__":
    unittest.main()

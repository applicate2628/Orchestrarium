import copy
import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from batchflow import MemoryStore, execute_batch, summarize_store


class BatchFlowTests(unittest.TestCase):
    def test_plan_is_not_mutated(self):
        store = MemoryStore()
        plan = [
            {"id": "z-first", "op": "append", "key": "audit", "value": "first"},
            {"id": "a-second", "op": "append", "key": "audit", "value": "second"},
        ]
        original = copy.deepcopy(plan)

        execute_batch(store, "B-plan", plan)

        self.assertEqual(plan, original)
        self.assertEqual(store.state["audit"], ["first", "second"])

    def test_completed_batch_is_idempotent(self):
        store = MemoryStore()
        plan = [{"id": "s1", "op": "inc", "key": "balance", "amount": 5}]

        execute_batch(store, "B-idem", plan)
        second = execute_batch(store, "B-idem", plan)

        self.assertEqual(second["status"], "already-complete")
        self.assertEqual(store.state["balance"], 5)
        self.assertEqual(len([event for event in store.events if event.get("type") == "committed"]), 1)

    def test_resume_after_crash_continues_after_checkpoint(self):
        store = MemoryStore()
        plan = [
            {"id": "s1", "op": "inc", "key": "n", "amount": 1},
            {"id": "s2", "op": "inc", "key": "n", "amount": 2},
            {"id": "s3", "op": "inc", "key": "n", "amount": 3},
        ]

        execute_batch(store, "B-crash", plan, crash_after="s2")
        execute_batch(store, "B-crash", plan)

        self.assertEqual(store.state["n"], 6)
        committed = [event["step_id"] for event in store.events if event.get("type") == "committed"]
        self.assertEqual(committed, ["s1", "s2", "s3"])

    def test_report_comes_from_journal(self):
        store = MemoryStore()
        execute_batch(store, "B-report", [{"id": "s1", "op": "set", "key": "x", "value": 1}])
        store.checkpoints.clear()

        summary = summarize_store(store)

        self.assertEqual(summary["committed"], 1)
        self.assertEqual(summary["batches"], ["B-report"])


if __name__ == "__main__":
    unittest.main()

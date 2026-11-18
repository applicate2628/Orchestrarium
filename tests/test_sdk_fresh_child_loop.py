"""Common loop recovery uses Host evidence, never another model decision."""
import asyncio
import json
import pytest
from test_sdk_child_loop import fixture
from sdk_execution import runtime


def test_fresh_received_intents_do_not_call_inference(monkeypatch):
    loop,calls=fixture(monkeypatch)
    def recover(assignment,worker,projection):
        return json.loads(worker.test_intent)
    loop._authority.recover_child_decision=recover
    async def forbidden(*args):raise AssertionError("recovered intent repeated inference")
    monkeypatch.setattr(runtime.SdkCoordinationWorker,"__call__",forbidden)
    assert asyncio.run(loop.run())=="archived-child"
    assert [x for x in calls if x.startswith("execute:")]==["execute:second","execute:first"]


def test_unknown_decision_returns_owner_reconciliation_without_inference(monkeypatch):
    loop,calls=fixture(monkeypatch)
    loop._authority.recover_child_decision=lambda *args:{"status":"needs-reconciliation","decision_run_ids":["unknown"]}
    async def forbidden(*args):raise AssertionError("unknown decision repeated inference")
    monkeypatch.setattr(runtime.SdkCoordinationWorker,"__call__",forbidden)
    assert asyncio.run(loop.run())=={"status":"needs-reconciliation","decision_run_ids":["unknown"],"child_id":"child"}
    assert not any(x.startswith("execute:") for x in calls)

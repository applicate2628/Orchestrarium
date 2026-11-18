"""Actual coordinator/executor composition with only SDK/model boundaries synthetic."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from test_sdk_copilot import make_executor, request
from test_sdk_coordinator import FakeAuthority, FakeSdk as CoordinatorSdk, FakeTool, FakeModel
from sdk_execution import coordinator


def composition(tmp_path, monkeypatch):
    authority = FakeAuthority()
    authority.current = request(cwd=str(tmp_path))
    executor, native, effects = make_executor(tmp_path, assert_current=authority.assert_current)
    outer = CoordinatorSdk()
    monkeypatch.setattr(coordinator, "_load_agents_sdk", lambda: (outer, FakeTool))
    instance = coordinator.AgentsCoordinator(
        model=FakeModel(), coordinator_binding=authority.current.coordinator_binding,
        authority=authority, executor=executor, max_turns=2,
    )
    return SimpleNamespace(authority=authority, executor=executor, native=native,
                           outer=outer, instance=instance)


def test_copilot_admitted_consultant_crosses_coordinator_without_claiming_receiving(tmp_path, monkeypatch):
    state = composition(tmp_path, monkeypatch)
    result = asyncio.run(state.instance.run("fixture-request"))
    output = json.loads(result.final_output)
    assert output == state.executor.execution_result.to_tool_output()
    assert output["status"] == "completed"
    assert output["task"]["content"] == "Bounded advice."
    assert output["review"] is None and output["authoritative"] is False
    assert output["process_settlement"] == "not_established"
    assert state.executor.execution_result.sdk_execution is None
    assert state.outer.model_calls == 1 and state.native.calls.count("send") == 1
    assert state.native.client_options["mode"] == "empty"
    assert state.native.client_options["github"]["use_logged_in_user"] is False
    assert state.native.runtime["path"] == str(tmp_path / "provisioned-runtime")
    assert state.native.options["tools"]["available_tools"] == []
    assert state.native.options["enable_config_discovery"] is False
    assert state.native.send_options["source"].agent_id == state.authority.current.coordinator_binding
    assert state.native.calls[-2:] == ["disconnect", "stop"]
    assert state.authority.effects[-1] == "executor_result"


def test_coordinator_refuses_export_after_root_revocation_without_replaying_copilot(tmp_path, monkeypatch):
    state = composition(tmp_path, monkeypatch)
    state.authority.denied.add("executor_result")
    with pytest.raises(PermissionError, match="current authority denied"):
        asyncio.run(state.instance.run("fixture-request"))
    acquired = state.executor.execution_result
    assert acquired is not None and acquired.task.content == "Bounded advice."
    assert state.native.calls.count("send") == 1 and state.outer.model_calls == 1
    assert state.native.calls[-2:] == ["disconnect", "stop"]
    assert state.authority.effects[-1] == "executor_result"
    assert acquired.to_tool_output()["authoritative"] is False

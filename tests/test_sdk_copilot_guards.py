"""Failure ownership and export boundaries; injected SDK only, no live runtime."""
import asyncio
from types import SimpleNamespace

import pytest

from test_sdk_copilot import FakeSdk, make_executor, request
from sdk_execution import copilot
from sdk_execution.copilot import CopilotError


def test_missing_runtime_refuses_before_lazy_sdk_loading(tmp_path, monkeypatch):
    sdk = FakeSdk()
    monkeypatch.setattr(copilot, "_load_sdk", lambda: pytest.fail("SDK import attempted"))
    missing = tmp_path / "absent-runtime"
    with pytest.raises(CopilotError, match="copilot_provisioned_runtime_required"):
        make_executor(tmp_path, sdk, runtime_path=str(missing))
    assert sdk.calls == []
    assert not missing.exists()
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("effect", ["copilot_start", "copilot_client_create"])
def test_current_host_denial_has_no_sdk_effects(tmp_path, effect):
    def denied(_request, current):
        if current == effect:
            raise ValueError("private Host rejection")
    executor, sdk, _ = make_executor(tmp_path, assert_current=denied)
    if effect == "copilot_start":
        with pytest.raises(CopilotError, match="copilot_authority_denied"):
            asyncio.run(executor.execute(request()))
    else:
        result = asyncio.run(executor.execute(request()))
        assert result.execution_error == "copilot_authority_denied"
        assert result.status == "incomplete"
    assert sdk.calls == []
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("stage", ["start", "create", "send"])
def test_sdk_exception_settles_acquired_owners_and_prevents_replay(tmp_path, stage):
    sdk = FakeSdk()
    sdk.failure = stage
    executor, _, _ = make_executor(tmp_path, sdk)
    result = asyncio.run(executor.execute(request()))
    assert result.status == "incomplete"
    assert result.execution_error == "copilot_sdk_failed"
    assert "private" not in str(result.to_dict())
    assert sdk.calls.count("stop") == 1
    assert sdk.calls.count("disconnect") == int(stage == "send")
    assert executor.execution_result is result
    before = list(sdk.calls)
    with pytest.raises(CopilotError, match="operation_already_consumed"):
        asyncio.run(executor.execute(request()))
    assert sdk.calls == before


@pytest.mark.parametrize("stage", ["disconnect", "stop"])
def test_cleanup_failure_preserves_acquired_task_without_false_completion(tmp_path, stage):
    sdk = FakeSdk()
    sdk.cleanup_failure = stage
    executor, _, _ = make_executor(tmp_path, sdk)
    result = asyncio.run(executor.execute(request()))
    assert result.status == "incomplete"
    assert result.provider_status == "completed"
    assert result.task.content == "Bounded advice."
    assert result.cleanup_error == "copilot_cleanup_failed"
    assert not result.protocol_closed
    assert "private" not in str(result.to_dict())
    assert sdk.calls.count("disconnect") == sdk.calls.count("stop") == 1
    assert executor.execution_result is result


def test_malformed_acquired_text_is_retained_without_fabricating_task(tmp_path):
    sdk = FakeSdk()
    sdk.content = "not a structured task"
    executor, _, _ = make_executor(tmp_path, sdk)
    result = asyncio.run(executor.execute(request()))
    assert result.status == "incomplete" and result.task is None
    assert result.observations and "not a structured task" in result.observations[0].payload_json
    assert sdk.calls[-3:] == ["unsubscribe", "disconnect", "stop"]
    assert executor.execution_result is result


def test_credential_echo_refuses_export_after_cleanup_and_keeps_private_evidence(tmp_path):
    sdk = FakeSdk()
    sdk.content = "fixture-credential"
    executor, _, _ = make_executor(tmp_path, sdk)
    with pytest.raises(ValueError, match="CREDENTIAL"):
        asyncio.run(executor.execute(request()))
    assert executor.execution_result is not None
    assert executor.execution_result.status == "incomplete"
    assert executor.execution_result.observations
    assert sdk.calls[-3:] == ["unsubscribe", "disconnect", "stop"]
    before = list(sdk.calls)
    with pytest.raises(CopilotError, match="operation_already_consumed"):
        asyncio.run(executor.execute(request()))
    assert sdk.calls == before


def test_cancellation_drains_acquired_session_and_never_acknowledges_fake_terminal(tmp_path):
    sdk = FakeSdk()
    executor, _, _ = make_executor(tmp_path, sdk)
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        async def blocked():
            entered.set()
            await release.wait()
        sdk.on_send = blocked
        running = asyncio.create_task(executor.execute(request()))
        await entered.wait()
        receipt = await executor.cancel("dispatch")
        assert receipt.acknowledged is False
        release.set()
        result = await running
        assert result.status == "interrupted"
        assert result.task.content == "Bounded advice."
        assert executor.execution_result is result
        assert sdk.calls.count("abort") == 1
        assert sdk.calls.count("disconnect") == sdk.calls.count("stop") == 1
        before = list(sdk.calls)
        with pytest.raises(CopilotError, match="operation_already_consumed"):
            await executor.execute(request())
        assert sdk.calls == before
    asyncio.run(scenario())


def test_wrong_terminal_event_type_cannot_supply_a_task(tmp_path):
    sdk = FakeSdk()
    original = sdk.send_and_wait
    async def wrong(*args, **kwargs):
        event = await original(*args, **kwargs)
        return SimpleNamespace(type="session.info", agent_id=None, data=event.data)
    sdk.send_and_wait = wrong
    executor, _, _ = make_executor(tmp_path, sdk)
    result = asyncio.run(executor.execute(request()))
    assert result.status == "incomplete" and result.task is None
    assert result.execution_error == "copilot_terminal_type_mismatch"
    assert sdk.calls[-3:] == ["unsubscribe", "disconnect", "stop"]


def test_unsafe_native_identity_is_not_exported_even_with_valid_task(tmp_path):
    sdk = FakeSdk()
    sdk.session_id = "fixture-credential"
    executor, _, _ = make_executor(tmp_path, sdk)
    with pytest.raises(ValueError, match="CREDENTIAL"):
        asyncio.run(executor.execute(request()))
    assert executor.execution_result.task.content == "Bounded advice."
    assert sdk.calls[-3:] == ["unsubscribe", "disconnect", "stop"]


def test_cancellation_during_start_prevents_session_acquisition(tmp_path):
    sdk = FakeSdk()
    executor, _, _ = make_executor(tmp_path, sdk)
    original = sdk.start
    async def cancel_during_start():
        await original()
        receipt = await executor.cancel("dispatch")
        assert receipt.acknowledged is False
    sdk.start = cancel_during_start
    result = asyncio.run(executor.execute(request()))
    assert result.status == "interrupted" and result.task is None
    assert "create" not in sdk.calls and "send" not in sdk.calls
    assert sdk.calls.count("stop") == 1
    assert executor.execution_result is result

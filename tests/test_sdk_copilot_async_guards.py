"""Deterministic async Host-permission races; no SDK or runtime process launch."""
import asyncio

import pytest

from test_sdk_copilot import make_executor, request
from sdk_execution.copilot import CopilotError


def test_concurrent_execute_during_async_admission_has_one_owner(tmp_path):
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        async def authority(_request, effect):
            if effect == "copilot_start":
                entered.set()
                await release.wait()
        executor, sdk, _ = make_executor(tmp_path, assert_current=authority)
        first = asyncio.create_task(executor.execute(request()))
        await entered.wait()
        second = asyncio.create_task(executor.execute(request()))
        # Yield exactly one scheduler turn, not a wall-clock race or sleep budget.
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        successful = [result for result in results if not isinstance(result, BaseException)]
        errors = [result for result in results if isinstance(result, BaseException)]
        assert len(successful) == len(errors) == 1
        assert successful[0].status == "completed"
        assert isinstance(errors[0], CopilotError)
        assert str(errors[0]) == "operation_already_consumed"
        assert sdk.calls.count("client") == sdk.calls.count("start") == sdk.calls.count("send") == 1
        assert sdk.calls.count("disconnect") == sdk.calls.count("stop") == 1
    asyncio.run(scenario())


@pytest.mark.parametrize("effect,forbidden", [
    ("copilot_start", "runtime"),
    ("copilot_client_create", "runtime"),
    ("copilot_session_create", "create"),
    ("copilot_profile_before", "profile"),
    ("copilot_send", "send"),
    ("copilot_profile_after", "profile"),
])
def test_cancel_during_awaited_permission_prevents_next_native_effect(tmp_path, effect, forbidden):
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        async def authority(_request, current):
            if current == effect:
                entered.set()
                await release.wait()
        executor, sdk, _ = make_executor(tmp_path, assert_current=authority)
        running = asyncio.create_task(executor.execute(request()))
        await entered.wait()
        calls_before_cancel = sdk.calls.count(forbidden)
        receipt = await executor.cancel("dispatch")
        release.set()
        outcome = await asyncio.gather(running, return_exceptions=True)
        assert receipt.requested and not receipt.acknowledged
        assert sdk.calls.count(forbidden) == calls_before_cancel
        if not isinstance(outcome[0], BaseException):
            assert outcome[0].status == "interrupted"
            if effect == "copilot_profile_after":
                assert outcome[0].task.content == "Bounded advice."
        else:
            assert isinstance(outcome[0], asyncio.CancelledError)
        if "client" in sdk.calls:
            assert sdk.calls.count("stop") == 1
        if "create" in sdk.calls:
            assert sdk.calls.count("disconnect") == 1
    asyncio.run(scenario())


@pytest.mark.parametrize("decision", ["deny", "true"])
def test_async_authority_denial_or_non_none_never_acquires_runtime(tmp_path, decision):
    async def authority(_request, effect):
        await asyncio.sleep(0)
        if decision == "deny":
            raise ValueError("private Host refusal")
        return True
    executor, sdk, _ = make_executor(tmp_path, assert_current=authority)
    expected = "copilot_authority_denied" if decision == "deny" else "copilot_invalid_authority_callback"
    with pytest.raises(CopilotError, match=expected):
        asyncio.run(executor.execute(request()))
    assert sdk.calls == []

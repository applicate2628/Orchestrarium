"""Optional offline integration with installed official ACP Connection/router.

Both endpoints use official Connection and an in-memory public message transport.
The peer is a source-shaped fixture, NOT MiMoCode or a provider/model process.
No SDK dependency is installed by this test. Missing ACP skips this module.
"""
import asyncio
import copy
from pathlib import Path
import sys

import pytest

pytest.importorskip('acp', reason='optional official ACP SDK is not installed')
from acp.core import Connection

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sdk_execution.contracts import ExecutionRequest
from sdk_execution.mimo import MimoAcpExchange

MODEL = 'mimo/offline-fixture'

class MemoryTransport:
    """Implements the public message transport send/receive/close contract."""
    def __init__(self):
        self.queue = asyncio.Queue()
        self.peer = None
        self.closed = False

    async def send(self, message):
        if self.closed:
            raise ConnectionError('closed test transport')
        await self.peer.queue.put(copy.deepcopy(message))

    async def receive(self):
        return await self.queue.get()

    async def close(self):
        if not self.closed:
            self.closed = True
            self.queue.put_nowait(None)
            self.peer.queue.put_nowait(None)


def request():
    return ExecutionRequest('work', 'mimo', 'dispatch', 'evidence', 'artifact', 'reviewer', MODEL,
        'low', '/fixture', 'subscription-fixture', 'review fixture', 'coordinator', ('fixture.py',))


async def exercise(*, malformed=False, collision=False, permission=False, delayed=False):
    left, right = MemoryTransport(), MemoryTransport()
    left.peer, right.peer = right, left
    callbacks_entered, release_callback = asyncio.Event(), asyncio.Event()

    class Exchange(MimoAcpExchange):
        async def session_update(self, session_id, update, **kwargs):
            # Block actual SDK callback dispatch, not the fixture's sending path.
            value = update.model_dump(by_alias=True) if hasattr(update, 'model_dump') else update
            if delayed and value.get('sessionUpdate') == 'agent_message_chunk':
                callbacks_entered.set()
                await release_callback.wait()
            await super().session_update(session_id, update, **kwargs)

    exchange = Exchange(assert_current=lambda req, effect: None)
    calls, permission_results = [], []
    peer = None

    async def handler(method, params, notification):
        calls.append(method)
        if method == 'initialize':
            return {'protocolVersion': 1, 'agentInfo': {'name': 'OpenCode'}}
        if method == 'session/new':
            await peer.send_notification('session/update', {'sessionId': 's', 'update': {
                'sessionUpdate': 'available_commands_update', 'availableCommands': []}})
            return {'sessionId': 's', 'models': {'currentModelId': MODEL, 'availableModels': [
                {'modelId': MODEL, 'name': 'Fixture'}, {'modelId': MODEL+'/low', 'name': 'Low'}]}}
        if method == 'session/set_model':
            assert params == {'sessionId': 's', 'modelId': MODEL+'/low'}
            return {'_meta': {'opencode': {'modelId': MODEL+'/low' if collision else MODEL,
                'variant': None if collision else 'low', 'availableVariants': ['low']}}}
        if method == 'session/prompt':
            if permission:
                permission_results.append(await peer.send_request('session/request_permission', {
                    'sessionId': 's', 'toolCall': {'toolCallId': 'tool-1', 'title': 'Read fixture',
                        'kind': 'read', 'status': 'pending'},
                    'options': [{'optionId': 'reject', 'name': 'Reject', 'kind': 'reject_once'}]}))
            update = {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'official transport answer'}}
            if malformed:
                update = {'sessionUpdate': 'not-a-real-update'}
            await peer.send_notification('session/update', {'sessionId': 's', 'update': update})
            return {'stopReason': 'end_turn'}
        raise AssertionError(method)

    peer = Connection(handler, right)
    connection = exchange.connect(left, None)
    operation = asyncio.create_task(exchange.run(request(), connection))
    try:
        if delayed:
            await asyncio.wait_for(callbacks_entered.wait(), 2)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert not operation.done(), 'prompt response overtook unfinished callback'
            release_callback.set()
        result = await asyncio.wait_for(operation, 3)
        return result, calls, permission_results
    finally:
        release_callback.set()
        await connection.close()
        await peer.close()
        if not operation.done():
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)


def test_official_connection_model_metadata_and_deferred_callback_drain():
    result, calls, _ = asyncio.run(exercise(delayed=True))
    assert result.native_result_text == 'official transport answer'
    assert result.native_thread_id == 's' and result.provider_status == 'completed'
    assert result.status == 'incomplete' and not result.protocol_closed
    assert result.execution_error == 'mimo_account_readback_unavailable'
    assert calls == ['initialize', 'session/new', 'session/set_model', 'session/prompt']


def test_official_router_adapts_permission_denial_response():
    result, _, permissions = asyncio.run(exercise(permission=True))
    assert permissions == [{'outcome': {'outcome': 'cancelled'}}]
    assert result.native_result_text == 'official transport answer'
    assert result.execution_error == 'mimo_account_readback_unavailable'


def test_official_schema_failure_drains_without_silent_completion():
    result, _, _ = asyncio.run(exercise(malformed=True))
    assert result.execution_error == 'mimo_callback_failed'
    assert result.native_result_text is None and result.native_thread_id == 's'
    assert result.status == 'incomplete'


def test_official_transport_does_not_confuse_slash_model_with_variant():
    result, calls, _ = asyncio.run(exercise(collision=True))
    assert result.execution_error == 'mimo_model_variant_mismatch'
    assert 'session/prompt' not in calls

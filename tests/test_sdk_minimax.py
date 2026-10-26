"""MiniMax source-shaped typed ACP fixtures; no CLI, account or SDK package calls."""
import asyncio
from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sdk_execution.contracts import ExecutionRequest
from sdk_execution.minimax import MiniMaxAcpAdapter, MiniMaxAcpError, MiniMaxAcpExchange

MODEL = 'm:minimax_api:fixture-model:u'


def request(**changes):
    base = ExecutionRequest('work', 'minimax', 'dispatch', 'evidence', 'artifact', 'reviewer',
                            MODEL, 'low', '/fixture', 'subscription-fixture', 'review fixture',
                            'coordinator', ('fixture.py',))
    return replace(base, **changes)


def options(model=MODEL, effort='low'):
    return {'configOptions': [
        {'id': 'permissionMode', 'type': 'select', 'currentValue': 'auto',
         'options': [{'value': 'auto', 'name': 'Automatic'}], '_meta': {'minimax-code/scope': 'process'}},
        {'id': 'model', 'type': 'select', 'currentValue': model,
         'options': [{'value': MODEL, 'name': 'Fixture'}]},
        {'id': 'thinkingEffort', 'type': 'select', 'currentValue': effort,
         'options': [{'value': x, 'name': x} for x in ['low', 'high']]},
    ]}


class Connection:
    def __init__(self, client):
        self.client = client
        self.calls = []
        self.config = options()
        self.cancelled = False
        self.closed = False

    async def initialize(self, protocol_version, client_capabilities=None):
        self.calls.append(('initialize', protocol_version, client_capabilities))
        return {'protocolVersion': 1, 'agentInfo': {'name': 'minimax-code', 'version': 'fixture'},
                'agentCapabilities': {'sessionCapabilities': {'close': {}}}}

    async def new_session(self, cwd, mcp_servers=None):
        self.calls.append(('new_session', cwd, mcp_servers))
        return {'sessionId': 'session-1', **self.config}

    async def set_config_option(self, config_id, session_id, value):
        self.calls.append(('set_config_option', config_id, session_id, value))
        for option in self.config['configOptions']:
            if option['id'] == config_id:
                option['currentValue'] = value
        await self.client.session_update(session_id, {'sessionUpdate': 'config_option_update', **self.config})
        return self.config

    async def prompt(self, session_id, prompt):
        self.calls.append(('prompt', session_id, prompt))
        await self.client.session_update(session_id, {'sessionUpdate': 'agent_message_chunk',
                                                     'content': {'type': 'text', 'text': 'fixture answer'}})
        return {'stopReason': 'end_turn'}

    async def cancel(self, session_id):
        self.calls.append(('cancel', session_id))
        self.cancelled = True

    async def close_session(self, session_id):
        self.calls.append(('close_session', session_id))
        return {}

    async def close(self):
        self.calls.append(('close',))
        self.closed = True


def run(connection_type=Connection, **changes):
    exchange = MiniMaxAcpExchange(assert_current=lambda req, effect: None)
    connection = connection_type(exchange)
    result = asyncio.run(exchange.run(request(**changes), connection))
    return result, connection, exchange


def test_minimax_uses_advertised_model_and_thinking_effort_not_grok_config():
    result, connection, _ = run(effort='high')
    assert result.status == 'incomplete' and result.review is None
    assert result.provider_status == 'completed' and result.native_result_text == 'fixture answer'
    assert result.execution_error == 'minimax_account_readback_unavailable'
    assert result.cleanup_error == 'minimax_process_settlement_unavailable'
    assert result.protocol_closed and connection.closed
    selected = [call[1] for call in connection.calls if call[0] == 'set_config_option']
    assert selected == ['model', 'thinkingEffort']
    assert connection.calls[0] == ('initialize', 1, {})
    assert ('new_session', '/fixture', []) in connection.calls
    assert not any(call[0] == 'authenticate' for call in connection.calls)


@pytest.mark.parametrize('change', ['missing_effort', 'unknown_model', 'readback_drift', 'duplicate_option'])
def test_bad_catalog_or_readback_never_reaches_prompt(change):
    class Bad(Connection):
        async def new_session(self, **kwargs):
            if change == 'missing_effort':
                self.config['configOptions'].pop()
            if change == 'unknown_model':
                self.config['configOptions'][1]['options'][0]['value'] = 'other'
            if change == 'duplicate_option':
                self.config['configOptions'].append(self.config['configOptions'][1])
            return await super().new_session(**kwargs)
        async def set_config_option(self, **kwargs):
            response = await super().set_config_option(**kwargs)
            if change == 'readback_drift':
                response['configOptions'][1]['currentValue'] = 'other'
            return response
    result, connection, _ = run(Bad)
    assert result.status == 'incomplete' and result.execution_error.startswith('minimax_')
    assert not any(call[0] == 'prompt' for call in connection.calls)
    assert connection.closed


@pytest.mark.parametrize('bad', ['session', 'configuration', 'unknown_update'])
def test_callback_failure_is_latched_even_when_sdk_handler_does_not_propagate(bad):
    class Bad(Connection):
        async def prompt(self, session_id, prompt):
            update = {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'do not trust'}}
            if bad == 'configuration':
                update = {'sessionUpdate': 'config_option_update', **options(model='other')}
            if bad == 'unknown_update':
                update = {'sessionUpdate': 'unknown'}
            await self.client.session_update('other' if bad == 'session' else session_id, update)
            return {'stopReason': 'end_turn'}
    result, _, _ = run(Bad)
    assert result.status == 'incomplete' and result.execution_error != 'minimax_account_readback_unavailable'
    assert result.review is None


def test_permissions_never_granted_and_session_mismatch_is_not_hidden():
    class Permission(Connection):
        async def prompt(self, session_id, prompt):
            for sid in (session_id, 'wrong'):
                answer = await self.client.request_permission(session_id=sid, tool_call={'title': 'fixture'},
                    options=[{'optionId': 'yes', 'kind': 'allow_once', 'name': 'yes'}])
                assert answer == {'outcome': {'outcome': 'cancelled'}}
            return {'stopReason': 'end_turn'}
    result, _, _ = run(Permission)
    assert result.execution_error == 'minimax_session_mismatch'


@pytest.mark.parametrize('change', [{'max_events': 1}, {'max_output_bytes': 64}])
def test_observation_limits_fail_closed(change):
    result, connection, _ = run(**change)
    assert result.capture_error in {'minimax_event_limit', 'minimax_output_limit'}
    assert connection.closed and result.status == 'incomplete'


def test_failed_session_close_never_becomes_clean_protocol():
    class Bad(Connection):
        async def close_session(self, session_id):
            raise RuntimeError('do not expose raw provider text')
    result, connection, _ = run(Bad)
    assert not result.protocol_closed and connection.closed
    assert 'do not expose' not in str(result)


def test_unadvertised_close_prevents_new_session():
    class Bad(Connection):
        async def initialize(self, **kwargs):
            return {'protocolVersion': 1, 'agentInfo': {'name': 'minimax-code'}, 'agentCapabilities': {}}
    result, connection, _ = run(Bad)
    assert result.execution_error == 'minimax_close_unavailable'
    assert not any(call[0] == 'new_session' for call in connection.calls)


def test_pre_cancelled_exchange_does_not_send_initialize():
    exchange = MiniMaxAcpExchange(assert_current=lambda req, effect: None)
    exchange.request_cancel()
    connection = Connection(exchange)
    result = asyncio.run(exchange.run(request(), connection))
    assert result.status == 'interrupted'
    assert connection.calls == [('close',)]


def test_unauthorized_effect_is_denied_and_errors_are_not_exported():
    def deny(req, effect):
        if effect == 'session/prompt':
            raise RuntimeError('secret fixture')
    exchange = MiniMaxAcpExchange(assert_current=deny)
    connection = Connection(exchange)
    result = asyncio.run(exchange.run(request(), connection))
    assert result.execution_error == 'minimax_authority_denied'
    assert not any(call[0] == 'prompt' for call in connection.calls)
    assert 'secret fixture' not in str(result)


def test_live_adapter_hold_is_before_any_connection_or_process_acquisition():
    calls = []
    adapter = MiniMaxAcpAdapter(client_factory=lambda client: calls.append(client), assert_current=lambda *a: None)
    with pytest.raises(MiniMaxAcpError, match='minimax_live_binding_unqualified'):
        asyncio.run(adapter.execute(request()))
    assert calls == []


def test_exchange_is_one_shot_even_after_failure():
    _, connection, exchange = run()
    with pytest.raises(MiniMaxAcpError, match='operation_already_consumed'):
        asyncio.run(exchange.run(request(), connection))


def test_acquired_session_is_closed_even_if_response_cannot_be_retained():
    result, connection, _ = run(max_events=1)
    assert result.capture_error == 'minimax_event_limit'
    assert ('close_session', 'session-1') in connection.calls


def test_duplicate_caller_cancellation_drains_owned_prompt_and_cleanup(monkeypatch):
    from sdk_execution import minimax
    monkeypatch.setattr(minimax, '_require_live_minimax_binding', lambda request: None)
    async def scenario():
        started, cancel_started, release_cancel = asyncio.Event(), asyncio.Event(), asyncio.Event()
        class Waiting(Connection):
            async def prompt(self, session_id, prompt):
                started.set()
                await release_cancel.wait()
                return {'stopReason': 'cancelled'}
            async def cancel(self, session_id):
                self.calls.append(('cancel', session_id))
                cancel_started.set()
                await release_cancel.wait()
        connections = []
        def factory(client):
            connection = Waiting(client)
            connections.append(connection)
            return connection
        adapter = MiniMaxAcpAdapter(client_factory=factory, assert_current=lambda *a: None)
        task = asyncio.create_task(adapter.execute(request()))
        await started.wait()
        task.cancel()
        await cancel_started.wait()
        task.cancel()
        await asyncio.sleep(0)
        release_cancel.set()
        result = await task
        assert result.status == 'interrupted' and result.protocol_closed
        assert connections[0].closed
        assert len([x for x in connections[0].calls if x[0] == 'cancel']) == 1
    asyncio.run(scenario())


def test_async_factory_is_rejected_before_acquisition():
    async def factory(client):
        pytest.fail('must not acquire')
    with pytest.raises(ValueError, match='synchronous'):
        MiniMaxAcpAdapter(client_factory=factory, assert_current=lambda *a: None)


def test_adapter_returns_bound_cancel_receipts_without_launching():
    adapter = MiniMaxAcpAdapter(client_factory=Connection, assert_current=lambda *a: None)
    receipt = asyncio.run(adapter.cancel('unknown'))
    assert not receipt.requested and receipt.error == 'unknown_execution'


@pytest.mark.parametrize('session_id,kind,expected', [
    ('session-1', 'available_commands_update', 'minimax_account_readback_unavailable'),
    ('wrong', 'available_commands_update', 'minimax_session_mismatch'),
    ('session-1', 'agent_message_chunk', 'minimax_invalid_setup_update'),
])
def test_commands_can_arrive_before_new_session_response_but_must_match_identity(session_id, kind, expected):
    class Early(Connection):
        async def new_session(self, **kwargs):
            await self.client.session_update(session_id, {'sessionUpdate': kind, 'availableCommands': []})
            return await super().new_session(**kwargs)
    result, _, _ = run(Early)
    assert result.execution_error == expected


def test_late_answer_during_close_cannot_mutate_terminal_text():
    class Late(Connection):
        async def close_session(self, session_id):
            await self.client.session_update(session_id, {'sessionUpdate': 'agent_message_chunk',
                'content': {'type': 'text', 'text': ' late corruption'}})
            return {}
    result, _, _ = run(Late)
    assert result.native_result_text == 'fixture answer'
    assert result.execution_error == 'minimax_invalid_content'


def test_permission_requests_consume_bounded_evidence_budget():
    class Flood(Connection):
        async def prompt(self, session_id, prompt):
            for _ in range(20):
                denied = await self.client.request_permission(session_id, {'title': 'fixture'}, [])
                assert denied == {'outcome': {'outcome': 'cancelled'}}
            return {'stopReason': 'end_turn'}
    result, _, _ = run(Flood, max_events=10)
    assert result.capture_error == 'minimax_event_limit'
    assert len(result.observations) <= 10
    assert any(x.kind == 'session/request_permission' for x in result.observations)

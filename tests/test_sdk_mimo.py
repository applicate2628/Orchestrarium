"""Source-shaped public ACP doubles, not installed SDK/provider qualification."""
import asyncio
from dataclasses import replace
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sdk_execution.contracts import ExecutionRequest
from sdk_execution.mimo import MimoAcpAdapter, MimoAcpError, MimoAcpExchange
MODEL = 'mimo/fixture'
def request(**changes):
    return replace(ExecutionRequest('work', 'mimo', 'dispatch', 'evidence', 'artifact', 'reviewer', MODEL,
        'low', '/fixture', 'subscription-fixture', 'review fixture', 'coordinator', ('fixture.py',)), **changes)

class Connection:
    def __init__(self, handler, writer, reader, *, observers):
        self.handler, self.observers, self.calls = handler, observers, []
        self.tasks = []
    async def update(self, session='s', text=None, delay=False):
        update = {'sessionUpdate': 'available_commands_update', 'availableCommands': []} if text is None else {
            'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': text}}
        params = {'sessionId': session, 'update': update}
        for observer in self.observers:
            observer(SimpleNamespace(direction='incoming', message={'method': 'session/update', 'params': params}))
        async def dispatch():
            if delay: await asyncio.sleep(0)
            await self.handler('session/update', params, True)
        self.tasks.append(asyncio.create_task(dispatch()))
    async def send_request(self, method, params):
        self.calls.append((method, params))
        if method == 'initialize':
            return {'protocolVersion': 1, 'agentInfo': {'name': 'OpenCode'}}
        if method == 'session/new':
            await self.update()
            return {'sessionId': 's', 'models': {'currentModelId': MODEL, 'availableModels': [
                {'modelId': MODEL}, {'modelId': MODEL+'/low'}]}, '_meta': {'opencode': {'modelId': MODEL, 'variant': None}}}
        if method == 'session/set_model':
            return {'_meta': {'opencode': {'modelId': MODEL, 'variant': 'low', 'availableVariants': ['low']}}}
        if method == 'session/prompt':
            await self.update(text='answer', delay=True)
            return {'stopReason': 'end_turn'}
        raise AssertionError(method)
    async def send_notification(self, method, params):
        self.calls.append((method, params))
    async def close(self):
        self.calls.append(('close', {}))
        await asyncio.gather(*self.tasks)

def router(client, *, use_unstable_protocol):
    assert use_unstable_protocol
    async def dispatch(method, params, notification):
        if method == 'session/update':
            await client.session_update(params['sessionId'], params['update'])
        elif method == 'session/request_permission':
            return await client.request_permission(params['sessionId'], {}, [])
        else: raise ValueError('unsupported')
    return dispatch

@pytest.fixture(autouse=True)
def sdk(monkeypatch):
    core, module = ModuleType('acp.core'), ModuleType('acp.client.router')
    core.Connection, module.build_client_router = Connection, router
    monkeypatch.setitem(sys.modules, 'acp.core', core)
    monkeypatch.setitem(sys.modules, 'acp.client.router', module)

def run(cls=Connection, **changes):
    sys.modules['acp.core'].Connection = cls
    ex = MimoAcpExchange(assert_current=lambda req, effect: None)
    async def scenario():
        conn = ex.connect(object(), object())
        return await ex.run(request(**changes), conn), conn, ex
    return asyncio.run(scenario())

def test_public_low_level_model_selection_and_notification_drain():
    result, conn, ex = run()
    assert result.native_result_text == 'answer' and result.native_thread_id == 's'
    assert result.status == 'incomplete' and result.provider_status == 'completed'
    assert result.execution_error == 'mimo_account_readback_unavailable'
    assert result.cleanup_error == 'mimo_process_settlement_unavailable' and not result.protocol_closed
    assert ex.observed_model == MODEL and ex.observed_effort == 'low'
    assert [m for m,p in conn.calls] == ['initialize','session/new','session/set_model','session/prompt','close']
    assert conn.calls[2][1] == {'sessionId': 's', 'modelId': MODEL+'/low'}
    assert conn.calls[1][1]['mcpServers'] == []

@pytest.mark.parametrize('mutation', ['collision','variant','catalog','missing'])
def test_readback_rejects_unproven_effort(mutation):
    class Bad(Connection):
        async def send_request(self, method, params):
            result = await super().send_request(method, params)
            if method == 'session/set_model':
                meta = result['_meta']['opencode']
                if mutation == 'collision': meta.update(modelId=MODEL+'/low', variant=None)
                if mutation == 'variant': meta['variant'] = 'high'
                if mutation == 'catalog': meta['availableVariants'] = []
                if mutation == 'missing': result = {}
            return result
    result, conn, _ = run(Bad)
    assert result.execution_error == 'mimo_model_variant_mismatch'
    assert 'session/prompt' not in [m for m,p in conn.calls]

def test_hold_before_factory():
    calls=[]
    adapter=MimoAcpAdapter(client_factory=lambda ex:calls.append(ex),assert_current=lambda *a:None)
    with pytest.raises(MimoAcpError,match='mimo_live_binding_unqualified'):
        asyncio.run(adapter.execute(request()))
    assert calls == []

def test_id_preserved_on_capture_limit():
    result, conn, _ = run(max_events=1)
    assert result.native_thread_id == 's' and result.capture_error == 'mimo_event_limit'
    assert conn.calls[-1][0] == 'close'

def test_foreign_early_update_rejected():
    class Foreign(Connection):
        async def send_request(self, method, params):
            if method == 'session/new': await self.update(session='foreign')
            return await super().send_request(method, params)
    result, conn, _ = run(Foreign)
    assert result.execution_error == 'mimo_session_mismatch'
    assert 'session/prompt' not in [m for m,p in conn.calls]

@pytest.mark.parametrize('kind', ['protocol','identity','catalog','duplicate','setter_error'])
def test_source_boundary_failures_no_prompt(kind):
    class Bad(Connection):
        async def send_request(self, method, params):
            if kind == 'setter_error' and method == 'session/set_model': raise RuntimeError('secret')
            response=await super().send_request(method, params)
            if method == 'initialize':
                if kind == 'protocol': response['protocolVersion'] = True
                if kind == 'identity': response['agentInfo']['name'] = 'mimo'
            if method == 'session/new':
                if kind == 'catalog': response['models']['availableModels'] = []
                if kind == 'duplicate': response['models']['availableModels'].append({'modelId':MODEL+'/low'})
            return response
    result, conn, _ = run(Bad)
    assert result.status == 'incomplete' and 'secret' not in str(result)
    assert 'session/prompt' not in [m for m,p in conn.calls] and conn.calls[-1][0] == 'close'

def test_permission_denied_and_late_terminal_text_frozen():
    class Late(Connection):
        async def send_request(self, method, params):
            if method == 'session/prompt':
                payload={'sessionId':'s'}
                for observer in self.observers:
                    observer(SimpleNamespace(direction='incoming', message={'method':'session/request_permission','id':10,'params':payload}))
                result=await self.handler('session/request_permission',payload,False)
                assert result == {'outcome': {'outcome': 'cancelled'}}
            return await super().send_request(method,params)
        async def close(self):
            await self.update(text='late')
            await super().close()
    result, _, _ = run(Late)
    assert result.native_result_text == 'answer' and result.execution_error == 'mimo_invalid_content'

def test_foreign_delayed_prompt_update_cannot_complete():
    class Foreign(Connection):
        async def send_request(self,method,params):
            if method == 'session/prompt':
                await self.update(session='foreign',text='wrong',delay=True)
                return {'stopReason':'end_turn'}
            return await super().send_request(method,params)
    result, _, _ = run(Foreign)
    assert result.native_result_text is None and result.execution_error == 'mimo_session_mismatch'

def test_router_validation_failure_drained_and_latched(monkeypatch):
    def bad_router(client, **kwargs):
        normal=router(client,**kwargs)
        async def dispatch(method,params,notification):
            if method == 'session/update' and params['update'].get('content'): raise ValueError('secret')
            return await normal(method,params,notification)
        return dispatch
    monkeypatch.setattr(sys.modules['acp.client.router'],'build_client_router',bad_router)
    result, _, _ = run()
    assert result.execution_error == 'mimo_callback_failed' and result.native_result_text is None

def test_broken_observer_cannot_be_silently_ignored():
    class Broken(Connection):
        async def send_request(self,method,params):
            if method == 'session/new':
                self.observers[0](object())
            return await super().send_request(method,params)
    result, conn, _ = run(Broken)
    assert result.execution_error == 'mimo_observer_failed'
    assert 'session/prompt' not in [m for m,p in conn.calls]

@pytest.mark.parametrize('changes', [{'max_output_bytes':20},{'prompt':'/compact'}])
def test_output_and_command_bounds(changes):
    result,conn,_=run(**changes)
    assert 'session/prompt' not in [m for m,p in conn.calls]
    assert result.status == 'incomplete'

def test_repeated_cancellation_drains_and_end_turn_not_ack(monkeypatch):
    import sdk_execution.mimo as module
    monkeypatch.setattr(module,'_require_live_mimo_binding',lambda req:None)
    async def scenario():
        entered,cancelling,release_cancel,release_prompt=[asyncio.Event() for _ in range(4)]
        class Delayed(Connection):
            async def send_request(self,method,params):
                if method == 'session/prompt':
                    entered.set()
                    await release_prompt.wait()
                    return {'stopReason':'end_turn'}
                return await super().send_request(method,params)
            async def send_notification(self,method,params):
                cancelling.set()
                await release_cancel.wait()
                await super().send_notification(method,params)
        sys.modules['acp.core'].Connection=Delayed
        connections=[]
        def factory(ex):
            conn=ex.connect(object(),object());connections.append(conn);return conn
        adapter=MimoAcpAdapter(client_factory=factory,assert_current=lambda *a:None)
        task=asyncio.create_task(adapter.execute(request()))
        await entered.wait();task.cancel();await cancelling.wait();task.cancel()
        release_cancel.set();await asyncio.sleep(0);task.cancel();release_prompt.set()
        result=await task
        assert result.status == 'interrupted' and not adapter.exchange.cancel_acknowledged
        assert connections[0].calls[-1][0] == 'close'
        assert [m for m,p in connections[0].calls].count('session/cancel') == 1
    asyncio.run(scenario())

def test_authority_each_effect_and_one_shot():
    async def scenario():
        effects=[]
        def authority(req,effect):
            effects.append(effect)
            if effect == 'session/prompt': raise RuntimeError('secret')
        ex=MimoAcpExchange(assert_current=authority)
        conn=ex.connect(object(),object())
        result=await ex.run(request(),conn)
        assert result.execution_error == 'mimo_authority_denied'
        assert effects == ['initialize','session/new','session/set_model','session/prompt']
        with pytest.raises(MimoAcpError,match='operation_already_consumed'): await ex.run(request(),conn)
    asyncio.run(scenario())

@pytest.mark.parametrize('mutation', ['non_string_variant', 'duplicate_variant', 'malformed_model'])
def test_catalog_metadata_requires_unambiguous_typed_values(mutation):
    class Malformed(Connection):
        async def send_request(self, method, params):
            response = await super().send_request(method, params)
            if mutation == 'malformed_model' and method == 'session/new':
                response['models']['availableModels'].append({'modelId': None})
            if method == 'session/set_model':
                variants = response['_meta']['opencode']['availableVariants']
                if mutation == 'non_string_variant': variants.append({})
                if mutation == 'duplicate_variant': variants.append('low')
            return response
    result, conn, _ = run(Malformed)
    assert 'session/prompt' not in [method for method, _ in conn.calls]
    assert result.execution_error in {'mimo_model_variant_unavailable', 'mimo_model_variant_mismatch'}

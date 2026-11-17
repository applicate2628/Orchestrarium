"""Synthetic callback contracts; no real provider or native CLI."""
import asyncio
import inspect
import pytest
from tests.test_sdk_kimi import prepared,offline_owner,fixtures
from sdk_execution.kimi import KimiAcpAdapter,KimiAdapterError

@pytest.mark.parametrize('slot',['assert_current','record'])
@pytest.mark.parametrize('kind',['coroutine_function','coroutine_callable','generator_function','generator_callable'])
def test_async_callback_refused_before_owner(tmp_path,monkeypatch,slot,kind):
    launch,request=prepared(tmp_path,monkeypatch)
    async def coroutine(*args):pass
    async def generator(*args):yield None
    class AsyncCallable:
        async def __call__(self,*args):pass
    class GeneratorCallable:
        async def __call__(self,*args):yield None
    callback={'coroutine_function':coroutine,'coroutine_callable':AsyncCallable(),'generator_function':generator,'generator_callable':GeneratorCallable()}[kind]
    options={'assert_current':lambda *_:None,'record':lambda *_:None,slot:callback}
    with pytest.raises(KimiAdapterError,match='synchronous_owner_callbacks_required'):
        KimiAcpAdapter(prevalidated=launch,**options)

@pytest.mark.parametrize('kind',['boolean','coroutine','async_generator'])
def test_non_none_record_result_cannot_claim_persisted_evidence(tmp_path,monkeypatch,kind):
    launch,request=prepared(tmp_path,monkeypatch)
    requests,_=offline_owner(monkeypatch,tmp_path,fixtures._FakeKimiAcpPeer())
    saved=[];returned=[]
    async def deferred():saved.append('not persisted')
    async def stream():yield 'not persisted'
    def record(_):
        result=True if kind=='boolean' else deferred() if kind=='coroutine' else stream()
        returned.append(result)
        return result
    instance=KimiAcpAdapter(prevalidated=launch,assert_current=lambda *_:None,record=record)
    try:
        result=asyncio.run(instance.execute(request))
        assert result.status=='incomplete',result.to_dict()
        assert result.provider_status=='completed'
        assert result.native_result_text=='artifact\nGATE: PASS\n'
        assert result.capture_error=='invalid_evidence_callback'
        assert len(result.observations)==1 and len(requests)==1 and saved==[]
        if kind=='coroutine':assert inspect.getcoroutinestate(returned[0])==inspect.CORO_CLOSED
        with pytest.raises(KimiAdapterError,match='operation_already_consumed'):
            asyncio.run(instance.execute(request))
    finally:
        for value in returned:
            if inspect.iscoroutine(value):value.close()

def test_sync_callback_none_is_still_supported(tmp_path,monkeypatch):
    launch,request=prepared(tmp_path,monkeypatch)
    offline_owner(monkeypatch,tmp_path,fixtures._FakeKimiAcpPeer())
    records=[]
    result=asyncio.run(KimiAcpAdapter(prevalidated=launch,assert_current=lambda *_:None,record=records.append).execute(request))
    assert result.status=='completed' and len(records)==1

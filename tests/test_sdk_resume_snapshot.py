"""Only fake SDK/authority; no official model or executor runtime."""
import asyncio
import copy
from types import SimpleNamespace
import pytest
from tests.test_sdk_coordinator import harness

@pytest.mark.parametrize('field',['max_turns','nested'])
def test_owner_mutation_during_restore_does_not_replace_claimed_snapshot(harness,monkeypatch,field):
    harness.authority.snapshot['history']={'items':[{'text':'claimed content'}]}
    expected=copy.deepcopy(harness.authority.snapshot)
    async def from_json(agent,state_json,*,context_override,strict_context):
        await asyncio.sleep(0)
        if field=='max_turns':harness.authority.snapshot['max_turns']=999
        else:harness.authority.snapshot['history']['items'][0]['text']='later content'
        harness.sdk.restorations.append({'snapshot':state_json})
        return SimpleNamespace(snapshot=state_json)
    monkeypatch.setattr(harness.sdk.RunState,'from_json',from_json)
    asyncio.run(harness.instance.resume('fixture-request','fixture-snapshot'))
    assert harness.sdk.restorations[0]['snapshot']==expected
    assert harness.sdk.calls[0]['input'].snapshot==expected
    assert harness.authority.claims==['fixture-snapshot']
    assert len(harness.executor.calls)==1 and harness.sdk.model_calls==0
    with pytest.raises(PermissionError,match='consumed'):
        asyncio.run(harness.instance.resume('fixture-request','fixture-snapshot'))

def test_deserializer_mutation_does_not_edit_owner_snapshot(harness,monkeypatch):
    harness.authority.snapshot['history']={'items':[{'text':'claimed'}]}
    expected=copy.deepcopy(harness.authority.snapshot)
    async def from_json(agent,state_json,*,context_override,strict_context):
        state_json['history']['items'][0]['text']='sdk normalization'
        return SimpleNamespace(snapshot=state_json)
    monkeypatch.setattr(harness.sdk.RunState,'from_json',from_json)
    asyncio.run(harness.instance.resume('fixture-request','fixture-snapshot'))
    assert harness.authority.snapshot==expected
    assert harness.authority.claims==['fixture-snapshot']

def test_tighter_bound_and_empty_nested_values_preserved(harness):
    harness.authority.snapshot.update(max_turns=1,history={'items':[],'metadata':None})
    expected=copy.deepcopy(harness.authority.snapshot)
    asyncio.run(harness.instance.resume('fixture-request','fixture-snapshot'))
    assert harness.sdk.restorations[0]['snapshot']==expected

"""Public transcript-bound continuation; native SDK/process peers are synthetic."""
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import pytest
from test_sdk_claude_dispatch import fixture as base_fixture
from test_sdk_claude import FakeClient, ClientBinding, SDK_VERSION
from test_sdk_copilot_dispatch import sealed_result
from test_sdk_continuation_dispatch import binding
from sdk_execution import claude, dispatch, runtime
from process_supervision import sdk_worker
from process_supervision.process_runner import ProcessRunnerV1


def prepare(tmp_path,monkeypatch):
    owner=runtime._owner()
    resolve=owner.resolve_provider_auth_configuration
    selected,path,environment,mutable=base_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(owner,"resolve_provider_auth_configuration",resolve)
    operation=dispatch.prepare_dispatch(selected,path,provider="claude",source_environment=environment,
                                         cancellation_probe=lambda:False)
    return operation,environment,mutable


class TranscriptPeer(FakeClient):
    def __init__(self, path, payload):
        super().__init__()
        self.transcript=path
        self.payload=payload
        self.init_change={"tools":[]}

    async def query(self, prompt, session_id="default"):
        self.active_session_id=session_id
        await super().query(prompt,session_id)
        with self.transcript.open("ab") as stream:
            stream.write(self.payload)

    def hook_input(self,event="Stop",**changes):
        return super().hook_input(event,session_id=self.active_session_id,
                                  transcript_path=str(self.transcript),**changes)

    async def receive_response(self):
        # The SDK resumes the selected session even though creation session_id is None.
        async for message in super().receive_response():
            if type(message).__name__=="SystemMessage":
                message=replace(message,data={**message.data,"session_id":self.active_session_id})
            elif type(message).__name__=="ResultMessage":
                message=replace(message,session_id=self.active_session_id)
            yield message


def execute_offline(operation,monkeypatch,peer):
    req=operation.request
    peer.terminal_change={"structured_output":dict(run_id=req.external_evidence_run_id,
        artifact_id=req.artifact_id,role=req.role,content="Bounded advice.")}
    def native_boundary(process,request,**kwargs):
        selected=runtime.runtime_selection_from_dict("claude",kwargs["runtime_selection"])
        class Sink:
            async def authorize(self,value,effect,*args):
                return kwargs["authority"](value,effect,*args)
            async def record(self,observation):pass
        def client_binding(options,**ignored):
            peer.options=options
            return ClientBinding(peer,SDK_VERSION)
        with monkeypatch.context() as patch:
            patch.setattr(claude.os,"environ",{row.name:row.value for row in kwargs["environment"]})
            patch.setattr(claude,"_official_client_binding",client_binding)
            result=asyncio.run(claude.create_claude_adapter(request,Sink(),selected).execute(request))
            assert result.status=="completed",result.execution_error
            return sealed_result(request,selected,result)
    monkeypatch.setattr(sdk_worker,"run_sdk_worker",native_boundary)
    with ProcessRunnerV1() as process:operation.execute(process)


def test_public_claude_transcript_restart_and_single_successor(tmp_path,monkeypatch):
    first,environment,_=prepare(tmp_path,monkeypatch)
    transcript=Path(first.selection.config_dir)/"session.jsonl"
    peer=TranscriptPeer(transcript,b"first observed transcript record\n")
    execute_offline(first,monkeypatch,peer)
    first_result=first.receive()
    assert first_result.terminal["status"]=="completed"
    artifact=Path(first.selection.work_item)/first.prevalidated.control.ledger_artifact
    document=json.loads(artifact.read_text())
    snapshot=document["native_continuation"]["transcript"]
    assert snapshot["sha256"]==hashlib.sha256(transcript.read_bytes()).hexdigest()
    assert snapshot["size"]==len(transcript.read_bytes())
    predecessor=first_result.terminal["runId"]
    selected=first.prevalidated
    path=Path(selected.control.sdk_task_binding)
    del first,first_result,document,peer

    def restore(source,artifact_name):
        selected.control.ledger_artifact=artifact_name+".json"
        selected.control.terminal_receipt=tmp_path/(artifact_name+"-terminal.json")
        path.write_text(json.dumps(binding(predecessorEvidenceRunId=source,artifactIdentity=artifact_name)))
        return dispatch.prepare_dispatch(selected,path,provider="claude",source_environment=dict(environment),
                                         cancellation_probe=lambda:False)

    successor=restore(predecessor,"successor")
    peer=TranscriptPeer(transcript,b"second observed transcript record\n")
    execute_offline(successor,monkeypatch,peer)
    received=successor.receive()
    assert received.terminal["status"]=="completed" and received.terminal["authorizing"] is False
    assert peer.options["resume"]==str(transcript)
    assert peer.calls.count("query")==1
    ledger=Path(successor.selection.work_item)/"agent-runs.jsonl"
    before=ledger.read_bytes()
    with pytest.raises(ValueError,match="already_consumed|transcript_changed"):
        repeat=restore(predecessor,"repeat")
        with ProcessRunnerV1() as process:repeat.execute(process)
    assert ledger.read_bytes()==before and peer.calls.count("query")==1

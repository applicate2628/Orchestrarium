"""Public durable continuation: actual owners, only native SDK/process synthetic."""
import json
from pathlib import Path
import pytest
from test_sdk_copilot_dispatch import prepare, execute_offline
from test_sdk_copilot import FakeSdk
from test_sdk_continuation_dispatch import binding
from sdk_execution import dispatch
from process_supervision.process_runner import ProcessRunnerV1




def test_public_consultant_receipt_restart_resume_and_single_successor(tmp_path,monkeypatch):
    first=prepare(tmp_path,monkeypatch)
    first_sdk=FakeSdk(); first_sdk.turn="first-observed-turn"
    execute_offline(first,monkeypatch,sdk=first_sdk)
    first_result=first.receive()
    assert first_result.terminal["status"]=="completed"
    first_artifact=Path(first.selection.work_item)/first.prevalidated.control.ledger_artifact
    document=json.loads(first_artifact.read_text())
    assert document["native_continuation"]["turn_id"]==first_sdk.turn
    assert document["native_continuation"]["thread_id"]==first_sdk.session_id
    predecessor=first_result.terminal["runId"]
    selected=first.prevalidated
    environment=dict(first._environment)
    path=Path(selected.control.sdk_task_binding)
    history=list(first_sdk.history)
    assert first_sdk.calls.count("create")==first_sdk.calls.count("send")==1
    del first, first_result, first_sdk, document

    def restore(source,artifact):
        selected.control.ledger_artifact=artifact+".json"
        selected.control.terminal_receipt=tmp_path/(artifact+"-terminal.json")
        path.write_text(json.dumps(binding(predecessorEvidenceRunId=source,artifactIdentity=artifact)))
        return dispatch.prepare_dispatch(selected,path,provider="copilot",source_environment=environment,
                                         cancellation_probe=lambda:False)

    successor=restore(predecessor,"successor")
    prior=successor.request.native_continuation
    assert prior.native_turn_id=="first-observed-turn"
    sdk=FakeSdk(); sdk.turn="next-observed-turn"; sdk.history=history
    execute_offline(successor,monkeypatch,sdk=sdk)
    received=successor.receive()
    assert received.terminal["status"]=="completed" and received.terminal["authorizing"] is False
    assert sdk.calls.count("resume")==sdk.calls.count("send")==1 and "create" not in sdk.calls
    assert successor.runtime_run.observation.result.native_turn_id=="next-observed-turn"
    ledger=Path(successor.selection.work_item)/"agent-runs.jsonl"
    before=ledger.read_bytes()
    repeat=restore(predecessor,"repeat")
    with ProcessRunnerV1() as process:
        with pytest.raises(ValueError,match="already_consumed"):
            repeat.execute(process)
    assert ledger.read_bytes()==before
    assert sdk.calls.count("send")==1


def test_public_copilot_fork_rejected_before_claim(tmp_path,monkeypatch):
    first=prepare(tmp_path,monkeypatch)
    selected=first.prevalidated
    path=Path(selected.control.sdk_task_binding)
    path.write_text(json.dumps(binding(contextMode="fork",predecessorEvidenceRunId="not-received")))
    ledger=Path(first.selection.work_item)/"agent-runs.jsonl"
    before=ledger.read_bytes() if ledger.exists() else None
    with pytest.raises(dispatch.DispatchError,match="E_COPILOT_SDK_PROMPT_ONLY_REQUIRED"):
        dispatch.prepare_dispatch(selected,path,provider="copilot",source_environment=dict(first._environment),
                                  cancellation_probe=lambda:False)
    assert (ledger.read_bytes() if ledger.exists() else None)==before

"""Real scoped grant/SDK loop/receiving/archive; native execution is synthetic."""
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from test_sdk_child_lead_authority import fixture,INSTANT,write_empty_bug_dispositions
from test_sdk_coordination import Client,adapter
from sdk_execution import runtime
from sdk_execution.contracts import ExecutionRequest,ExecutionResult,TaskResult,json_text
from sdk_execution.coordination import CoordinationInferenceRequest,child_coordination_payload,child_choice_sha256
from sdk_execution.coordinator import ChildLeadCoordinator
from sdk_execution.worker import encode_frame
from process_supervision import process_runner as processes
from process_supervision import sdk_worker
from provider_prompt import ProviderOutputContext,assemble_external_prompt


def test_actual_child_selects_executes_receives_and_archives_only_child(tmp_path,monkeypatch):
    authority,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    task=requests["task-one"]
    selection=selections["task-one"]
    counts={"decisions":0,"tasks":0}
    monkeypatch.setattr(runtime,"prepare_environment",lambda *args:({},ProviderOutputContext(())))
    monkeypatch.setattr(runtime._owner(),"require_codex_hook_trust",lambda *args,**kwargs:0)
    original_worker=sdk_worker.run_sdk_worker

    def native_boundary(process,request,**kwargs):
        selected=runtime.runtime_selection_from_dict("codex",kwargs["runtime_selection"])
        if type(request) is CoordinationInferenceRequest:
            state=json.loads(request.child_choice_json)
            done="task-one" in state["completed_request_ids"]
            text=json_text({"operation_id":request.operation_id,
                "child_choice_sha256":child_choice_sha256(request.child_choice_json),
                "action":"finish" if done else "execute","request_id":None if done else "task-one"})
            client=Client(request,text=text)
            instance=adapter(client,lambda req,effect:kwargs["authority"](req,effect))
            instance._request=request;instance._used=True
            result=instance._execute(request,None)
            assert result.status=="completed",result.execution_error
            kind="coordination_result";counts["decisions"]+=1
        else:
            reported=runtime.selected_sdk_execution(request,selected)
            reported={key:value for key,value in reported.items() if key not in {"schemaVersion","requestSha256"}}
            reported.update(schemaVersion=1,sdkVersion="fixture",runtimeVersion="fixture")
            result=ExecutionResult(request=request,status="completed",provider_status="completed",protocol_closed=True,
                native_thread_id="child-task-thread",native_turn_id="child-task-turn",
                sdk_execution_json=json_text(reported),
                task=TaskResult(request.external_evidence_run_id,request.artifact_id,request.role,"Completed scoped task."))
            kind="result";counts["tasks"]+=1
        def simulated_run(process_request,*,dialogue):
            frames=iter([*[encode_frame({"kind":"observation","run_id":request.run_id,"observation":obs.to_dict()}) for obs in result.observations],
                         encode_frame({"kind":kind,"result":result.to_dict()})])
            class Channel:
                def write_line(self,value):pass
                def read_line(self):
                    try:return next(frames)
                    except StopIteration:raise EOFError()
            dialogue.handler(Channel())
            failed=processes._request_failure(process_request,processes.ProcessSupervisionError("PSV1-INTERNAL","execution"),time.monotonic())
            return replace(failed,outcome="success",terminal_stage="completed",failure_id=None,target_exit_code=0,
                resources_closed=True,policy_id="sdk-worker-v1",
                tree=processes.TreeObservationV1("synthetic",True,"EMPTY",True,True,True,True))
        with patch.object(process,"run",side_effect=simulated_run):
            return original_worker(process,request,**kwargs)
    monkeypatch.setattr(sdk_worker,"run_sdk_worker",native_boundary)
    with processes.ProcessRunnerV1() as process:
        common=dict(authority=authority,process_owner=process,source_environment={},
                    deadline_monotonic=time.monotonic()+600,cancellation_probe=lambda:False,started_at=INSTANT)
        executor=runtime.SdkReviewExecutor(request_id="task-one",selection=selection,artifact="task-result.json",**common)
        decision_number=0
        def factory(admitted,projection):
            nonlocal decision_number
            decision_number+=1
            key="decision-"+str(decision_number)
            system="Choose the next scoped admitted task or finish after received evidence."
            payload=child_coordination_payload(key,system,projection)
            values={**task.to_dict(),"scope":task.scope,"role":"lead","result_kind":"review",
                "external_dispatch_id":key+"-dispatch","external_evidence_run_id":key+"-evidence","artifact_id":key,
                "prompt":assemble_external_prompt(payload.encode()).decode(),
                "operation_id":key,"admitted_request_id":assignment.child_id,
                "outer_budget_id":key+"-outer","inner_budget_id":key+"-inner",
                "inner_request_sha256":hashlib.sha256(projection.encode()).hexdigest(),
                "system_instructions":system,"child_choice_json":projection}
            requests[key]=CoordinationInferenceRequest(**values)
            chosen=replace(selection,config_overrides=runtime.CODEX_BOUNDED_REVIEW_OVERRIDES)
            return runtime.SdkCoordinationWorker(request_id=key,selection=chosen,artifact=key+".json",**common)
        write_empty_bug_dispositions(tmp_path,"child-lane",INSTANT)
        loop=ChildLeadCoordinator(child_id=assignment.child_id,authority=authority,
                                 decision_factory=factory,executors={"task-one":executor})
        archived=asyncio.run(loop.run())
    assert counts=={"decisions":2,"tasks":1}
    assert Path(archived).is_dir() and "archive" in Path(archived).parts
    assert Path(root.work_item).is_dir() and not Path(assignment.child_work_item).exists()
    events=[json.loads(line) for line in (Path(archived)/"agent-runs.jsonl").read_text().splitlines()]
    assert len([row for row in events if row.get("eventKind")=="terminal"])==3
    assert all(row.get("authorizing") is False for row in events if row.get("eventKind")=="terminal")
    assert executor.terminal["status"]=="completed"

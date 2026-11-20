"""Real scoped grant/SDK loop/receiving/archive; native execution is synthetic."""
import asyncio
import pytest
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


@pytest.mark.parametrize("initial_catalog", ["seeded", "empty", "restored"])
def test_actual_proposal_root_admission_restart_execution_and_archive(tmp_path,monkeypatch,initial_catalog):
    if initial_catalog != "seeded":
        from types import SimpleNamespace
        from test_sdk_runtime import fixture as root_fixture
        from test_mutate_work_item import quick_status, closure
        template,root=root_fixture(tmp_path)
        root_item=Path(root.work_item);(root_item/"status.md").write_text(quick_status())
        child=root_item.parent/"child-lane";child.mkdir();(child/"status.md").write_text(quick_status())
        # A Host configuration template is not registered or executable.
        task=runtime.prepare_codex_request(replace(template,work_item_id=child.name,cwd=str(child),
            role="consultant",result_kind="task",coordinator_binding="child-coordinator"))
        selection=replace(root,work_item=str(child))
        requests={};selections={}
        root_owner=SimpleNamespace(resolve=lambda key:requests[key],assert_current=lambda req,effect:None)
        base_root_owner=root_owner
        if initial_catalog=="restored":
            root_owner=runtime.RootTaskRegistry(root_authority=base_root_owner,root_selection=root,source_environment={})
        assignment=runtime.publish_child_assignment(root_selection=root,root_authority=root_owner,selections={},
            child_id="child-grant",coordinator_binding=task.coordinator_binding,scope=task.scope,
            required_request_ids=(),child_work_item=str(child),goal="Investigate the remaining scoped case.",
            context="Root background without an executable seed.",
            lifecycle_permissions=("delegate","finish","cancel","delegate-child"),
            artifact="child-assignment.json",started_at=INSTANT,decision_session_mode="native-persistent",
            decision_selection=replace(selection,config_overrides=runtime.CODEX_BOUNDED_REVIEW_OVERRIDES))
        authority=runtime.ChildLeadAuthority(root_authority=root_owner,root_selection=root,child_id=assignment.child_id,
            selections={},closure_data=closure(INSTANT).encode(),terminal_instant=INSTANT,repository_root=tmp_path)
        assert assignment.request_ids==() and authority.child_catalog(assignment)==()
    else:
        original_publish=runtime.publish_child_assignment
        with patch.object(runtime,"publish_child_assignment",side_effect=lambda **kwargs: original_publish(**kwargs,decision_session_mode="native-persistent")):
            authority,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
        task=requests["task-one"]
        selection=selections["task-one"]
    counts={"decisions":0,"tasks":0}
    native_history=[]
    native_calls=[]
    monkeypatch.setattr(runtime,"prepare_environment",lambda *args:({},ProviderOutputContext(())))
    monkeypatch.setattr(runtime._owner(),"require_codex_hook_trust",lambda *args,**kwargs:0)
    original_worker=sdk_worker.run_sdk_worker

    def native_boundary(process,request,**kwargs):
        selected=runtime.runtime_selection_from_dict("codex",kwargs["runtime_selection"])
        if type(request) is CoordinationInferenceRequest:
            state=json.loads(request.child_choice_json)
            outcomes=state["proposal_results"]
            pending=[row["request_id"] for row in state["catalog"] if row["request_id"] not in state["completed_request_ids"]]
            if not outcomes:
                action="propose";request_id=None
                proposal={"proposal_id":"extra-analysis","role":"consultant","prompt":"Check the remaining scoped case.","scope":list(task.scope)}
            elif pending:
                action="execute";request_id=pending[0];proposal=None
            else:
                action="finish";request_id=None;proposal=None
            text=json_text({"operation_id":request.operation_id,
                "child_choice_sha256":child_choice_sha256(request.child_choice_json),
                "action":action,"request_id":request_id,"proposal":proposal})
            class PersistentClient(Client):
                def thread_start(self,params):
                    assert params["ephemeral"] is False
                    native_calls.append("start")
                    return super().thread_start(params)
                def thread_resume(self,thread_id,params):
                    assert thread_id=="thread-1"
                    native_calls.append("resume")
                    return super().thread_start(params)
                def thread_read(self,thread_id,include_turns=False):
                    return {"thread":{"id":thread_id,"turns":list(native_history)}}
                def turn_start(self,thread_id,input_items,params):
                    value=super().turn_start(thread_id,input_items,params)
                    turn_id="decision-turn-"+str(counts["decisions"]+1)
                    value["turn"]["id"]=turn_id
                    for event in self.events:
                        payload=event["payload"]
                        if "turnId" in payload:payload["turnId"]=turn_id
                        if "turn" in payload:payload["turn"]["id"]=turn_id
                    return value
            client=PersistentClient(request,text=text)
            instance=adapter(client,lambda req,effect:kwargs["authority"](req,effect))
            instance._request=request;instance._used=True
            result=instance._execute(request,None)
            assert result.status=="completed",result.execution_error
            native_history.append({"id":result.native_turn_id,"status":"completed","error":None})
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
        # The actual filesystem/ledger path took >7 minutes for the first
        # received decision in this fixture. Cover all six operations, rather
        # than timing out later pre-created executors before their turn.
        common=dict(authority=authority,process_owner=process,source_environment={},
                    deadline_monotonic=time.monotonic()+3600,cancellation_probe=lambda:False,started_at=INSTANT)
        initial_executors=({} if initial_catalog!="seeded" else {
            "task-one":runtime.SdkReviewExecutor(request_id="task-one",selection=selection,artifact="task-result.json",**common)})
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
            values["decision_session_mode"]="native-persistent"
            chosen=replace(selection,config_overrides=runtime.CODEX_BOUNDED_REVIEW_OVERRIDES)
            requests[key]=authority.prepare_child_decision(admitted,CoordinationInferenceRequest(**values),chosen)
            return runtime.SdkCoordinationWorker(request_id=key,selection=chosen,artifact=key+".json",**common)
        write_empty_bug_dispositions(tmp_path,"child-lane",INSTANT)
        loop=ChildLeadCoordinator(child_id=assignment.child_id,authority=authority,
                                 decision_factory=factory,executors=initial_executors)
        pending=asyncio.run(loop.run())
        assert pending["status"]=="needs-admission"
        assert counts==({"decisions":1,"tasks":0} if initial_catalog!="seeded" else {"decisions":2,"tasks":1})
        candidate=runtime.prepare_codex_request(replace(task,external_dispatch_id="extra-dispatch",external_evidence_run_id="extra-evidence",
            artifact_id="extra-artifact",prompt="Check the remaining scoped case."))
        from test_mutate_work_item import closure
        task_key="task-two"
        if initial_catalog=="restored":
            registry=authority._root_authority
            outcome=registry.admit(authority=authority,proposal_id="extra-analysis",request=candidate,
                selection=selection,artifact="extra-admission.json",started_at=INSTANT)
            task_key=outcome["request_id"]
            assert outcome["status"]=="accepted"
            # Discard all ephemeral request/registry state. The new owner must
            # restore the concrete accepted request, not ask Root to reroute it.
            requests.clear();selections.clear()
            registry=runtime.RootTaskRegistry(root_authority=base_root_owner,root_selection=root,source_environment={})
            restored_authority=runtime.ChildLeadAuthority(root_authority=registry,root_selection=root,
                child_id=assignment.child_id,selections={},closure_data=closure(INSTANT).encode(),
                terminal_instant=INSTANT,repository_root=tmp_path)
            restoration=registry.restore(restored_authority)
            assert restoration["unavailable"]=={}
            selections=restoration["selections"]
            assert set(selections)=={task_key}
            assert task_key not in requests
            restored=registry.resolve(task_key)
            assert restored.prompt==candidate.prompt and restored.model==candidate.model
            assert restored.scope==candidate.scope and restored.role==candidate.role
            root_owner=registry
        else:
            requests[task_key]=candidate;selections[task_key]=selection
            runtime.publish_child_task_admission(authority=authority,proposal_id="extra-analysis",request_id=task_key,
                selection=selection,accepted=True,artifact="extra-admission.json",started_at=INSTANT)
            root_owner=authority._root_authority
        authority=runtime.ChildLeadAuthority(root_authority=root_owner,root_selection=root,
            child_id=assignment.child_id,selections=selections,closure_data=closure(INSTANT).encode(),
            terminal_instant=INSTANT,repository_root=tmp_path)
        common["authority"]=authority
        common["deadline_monotonic"]=time.monotonic()+3600
        executors={key:runtime.SdkReviewExecutor(request_id=key,selection=selected,
            artifact=key+"-result.json",**common) for key,selected in selections.items()}
        loop=ChildLeadCoordinator(child_id=assignment.child_id,authority=authority,
            decision_factory=factory,executors=executors)
        archived=asyncio.run(loop.run())
    assert counts==({"decisions":3,"tasks":1} if initial_catalog!="seeded" else {"decisions":4,"tasks":2})
    assert native_calls==["start"]+["resume"]*(counts["decisions"]-1)
    assert len({row["id"] for row in native_history})==counts["decisions"]
    assert Path(archived).is_dir() and "archive" in Path(archived).parts
    assert Path(root.work_item).is_dir() and not Path(assignment.child_work_item).exists()
    events=[json.loads(line) for line in (Path(archived)/"agent-runs.jsonl").read_text().splitlines()]
    assert len([row for row in events if row.get("eventKind")=="terminal"])==counts["decisions"]+counts["tasks"]
    assert all(row.get("authorizing") is False for row in events if row.get("eventKind")=="terminal")
    assert executors[task_key].terminal["status"]=="completed"
    if initial_catalog=="restored":
        assert sum(row.get("eventKind")=="launch" and row.get("runId")==restored.external_dispatch_id for row in events)==1
        assert task_key not in requests

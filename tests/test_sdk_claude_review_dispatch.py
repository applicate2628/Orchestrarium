"""Claude prompt-only reviewer through existing owners; no native model calls."""
from dataclasses import replace
from pathlib import Path
import pytest
from test_sdk_claude_dispatch import fixture as task_fixture, owner, dispatch, runtime
import test_sdk_receiving as evidence
from sdk_execution.contracts import ReviewResult
from sdk_execution.receiving import terminal_payload


def fixture(tmp_path, monkeypatch, role="qa-engineer"):
    selected,path,env,mutable=task_fixture(tmp_path,monkeypatch)
    c=selected.control
    c.sdk_task_binding=None
    c.sdk_review_binding=path
    c.ledger_role=role
    selected=replace(selected,role_provenance=owner.external_role_provenance(c,"claude"))
    return selected,path,env,mutable


def prepare(tmp_path,monkeypatch,**kwargs):
    selected,path,env,mutable=fixture(tmp_path,monkeypatch,**kwargs)
    return dispatch.prepare_dispatch(selected,path,provider="claude",source_environment=env,cancellation_probe=lambda:False)


def observed(monkeypatch,req,selection,verdict="PASS",process=None):
    selected=runtime.selected_sdk_execution(req,selection)
    config={k:v for k,v in selected.items() if k not in {"schemaVersion","requestSha256"}}
    config.update(schemaVersion=1,sdkVersion="fixture",runtimeVersion="fixture")
    return evidence.synthetic_observation(monkeypatch,req,runtime_selection=selection.to_dict(),sdk_config=config,
        review=ReviewResult(req.external_evidence_run_id,req.artifact_id,req.role,verdict,()),
        alter_process=(lambda p:replace(p,**process)) if process else None)


def test_review_selection_and_output_schema(tmp_path,monkeypatch):
    op=prepare(tmp_path,monkeypatch)
    assert op.request.result_kind=="review" and op.request.tool_profile=="prompt-only"
    assert runtime.execution_role(op.request)=="external-reviewer"
    data=dict(run_id=op.request.external_evidence_run_id,artifact_id=op.request.artifact_id,role=op.request.role,verdict="PASS",findings=[])
    assert op._authorize_tool(op.request,"StructuredOutput",data) is None
    for bad in [{**data,"run_id":"wrong"},{**data,"content":"task"},{**data,"role":"consultant"}]:
        with pytest.raises(ValueError):op._authorize_tool(op.request,"StructuredOutput",bad)
    with pytest.raises(ValueError):op._authorize_tool(op.request,"Read",{})


@pytest.mark.parametrize("role",["consultant","backend-engineer"])
def test_nonreview_roles_rejected_before_admission(tmp_path,monkeypatch,role):
    with pytest.raises(ValueError):prepare(tmp_path,monkeypatch,role=role)


def test_cli_review_selector_reaches_shared_owner(tmp_path,monkeypatch):
    fixture(tmp_path,monkeypatch)
    class Reached(Exception):pass
    def prep(selected,path,**kwargs):
        assert kwargs["provider"]=="claude"
        assert selected.role_provenance.execution_role=="external-reviewer"
        raise Reached()
    monkeypatch.setattr(dispatch,"prepare_dispatch",prep)
    with pytest.raises(Reached):
        owner.launch("claude",["review","--sdk-review-binding","binding.json","--terminal-receipt","receipt.json","--ledger-role","qa-engineer","--","-p","--output-format","text","--model","claude-opus-4-7","--effort","high"])


@pytest.mark.parametrize("verdict",["PASS","REVISE"])
def test_runtime_receiving_preserves_review_gate_without_authority(tmp_path,monkeypatch,verdict):
    import process_supervision.sdk_worker as worker
    from process_supervision.process_runner import ProcessRunnerV1
    op=prepare(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,"prepare_environment",lambda *a:({},owner.ProviderOutputContext(())))
    calls=[]
    def simulated(process,req,**kwargs):
        calls.append(req)
        for effect in dispatch._CLAUDE_STAGES[4:]:
            if effect=="account":
                phase={5:"before_connect",7:"initialize",9:"system_init"}[op._stage]
                kwargs["authority"](req,effect,{"kind":"account","evidence":{"phase":phase,"data":{}}})
            else:kwargs["authority"](req,effect)
        selection=runtime.runtime_selection_from_dict("claude",kwargs["runtime_selection"])
        return observed(monkeypatch,req,selection,verdict)
    monkeypatch.setattr(worker,"run_sdk_worker",simulated)
    with ProcessRunnerV1() as process:op.execute(process)
    result=op.receive()
    assert result.terminal["gate"]==verdict
    assert result.terminal["executionRole"]=="external-reviewer"
    assert result.terminal["authorizing"] is False and result.terminal["closesRunIds"]==[]
    assert len(calls)==1
    with pytest.raises(ValueError):op.execute(object())


@pytest.mark.parametrize("process",[{"cancelled":True},{"target_exit_code":1}])
def test_failed_review_never_produces_pass(tmp_path,monkeypatch,process):
    op=prepare(tmp_path,monkeypatch)
    obs=observed(monkeypatch,op.request,op.selection,process=process)
    result=terminal_payload(op.request,obs,output_context=owner.ProviderOutputContext(()),admitted_sdk_execution=runtime.selected_sdk_execution(op.request,op.selection))
    assert result["status"]=="blocked" and result["gate"]=="none"


def test_prompt_review_requires_retained_selected_commitment(tmp_path,monkeypatch):
    op=prepare(tmp_path,monkeypatch)
    obs=observed(monkeypatch,op.request,op.selection)
    with pytest.raises(ValueError,match="commitment"):
        terminal_payload(op.request,obs,output_context=owner.ProviderOutputContext(()))
    selected=runtime.selected_sdk_execution(op.request,op.selection)
    selected["requestSha256"]="0"*64
    with pytest.raises(ValueError,match="commitment"):
        terminal_payload(op.request,obs,output_context=owner.ProviderOutputContext(()),admitted_sdk_execution=selected)


def test_actual_review_adapter_output_callback_order(tmp_path,monkeypatch):
    import asyncio
    import test_sdk_claude as native
    op=prepare(tmp_path,monkeypatch)
    op._consumed=True
    for effect in dispatch._CLAUDE_STAGES[:4]:op.assert_current(op.request,effect)
    client=native.FakeClient()
    client.init_change["tools"]=[native.OUTPUT_TOOL]
    data=dict(run_id=op.request.external_evidence_run_id,artifact_id=op.request.artifact_id,role=op.request.role,verdict="PASS",findings=[])
    client.terminal_change["structured_output"]=data
    def verify(req,value):
        op.assert_current(req,"account")
        return op._verify_auth_context(req,value)
    def authorize(req,name,args):
        op.assert_current(req,"tool")
        return op._authorize_tool(req,name,args)
    async def output():
        args=dict(tool_name=native.OUTPUT_TOOL,tool_input=data)
        decision=await client.hook("PreToolUse",**args)
        assert decision["hookSpecificOutput"]["permissionDecision"]=="allow"
        await client.hook("PostToolUse",**args)
    client.before_terminal=output
    instance,_=native.adapter(client,authority=op.assert_current,authorize=authorize,verify=verify,instructions=lambda req:op.selection.instructions)
    result=asyncio.run(instance.execute(op.request))
    assert result.status=="completed" and result.review.verdict=="PASS" and result.task is None
    assert client.options["tools"]==[]


def test_receiving_artifact_repair_uses_retained_review_not_new_execution(tmp_path,monkeypatch):
    from sdk_execution.receiving import receive_terminal
    from test_agent_run_ledger import run_ledger, run_validator
    from test_sdk_claude_consultant_receiving import options
    op=prepare(tmp_path,monkeypatch)
    item=Path(op.selection.work_item)
    admission=run_ledger(item,*runtime.build_launch_arguments(op.request,op.selection,started_at="2026-10-23T10:01:00Z"))
    assert admission.returncode==0,admission.stdout+admission.stderr
    obs=observed(monkeypatch,op.request,op.selection)
    selected=runtime.selected_sdk_execution(op.request,op.selection)
    body=terminal_payload(op.request,obs,output_context=owner.ProviderOutputContext(()),admitted_sdk_execution=selected)
    artifact=item/"reviews/qa.md"
    artifact.write_bytes(b"incorrect artifact")
    before=(item/"agent-runs.jsonl").read_bytes()
    with pytest.raises(ValueError):receive_terminal(item,op.request,obs,**options())
    assert (item/"agent-runs.jsonl").read_bytes()==before
    artifact.write_bytes((body["resultText"]+"\n").encode())
    result=receive_terminal(item,op.request,obs,**options())
    assert result["gate"]=="PASS" and result["authorizing"] is False
    assert run_validator(item).returncode==0


@pytest.mark.parametrize("args",[["--sdk-review-binding","r","--sdk-task-binding","t"],["--sdk-review-binding","r"]])
def test_selector_conflict_or_unsupported_provider(args):
    with pytest.raises(ValueError):owner.parse_control(args, external=True, provider="claude" if len(args)>2 else "kimi")

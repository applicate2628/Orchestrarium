"""Prompt-only Claude CLI preparation/owners, no provider process or network."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_sdk_dispatch import fixture as codex_fixture, binding, owner, dispatch, runtime


def fixture(tmp_path, monkeypatch, *, mode="claude-direct", model="claude-opus-4-7"):
    prior, path, _ = codex_fixture(tmp_path, monkeypatch, ledger_role="consultant")
    c = prior.control
    c.sdk_task_binding = path
    c.provider_flags = ["-p","--output-format","text","--model",model,"--effort","high"]
    flags, model, effort = owner.resolved_profile("claude", c.provider_flags)
    selected = owner.PolicyBoundLaunch(c,"fixture",tuple(flags),model,effort,owner.external_role_provenance(c,"claude"),None)
    config = tmp_path / "claude-config"; config.mkdir()
    capture = tmp_path / "claude-capture"; capture.mkdir()
    monkeypatch.setenv("CLAUDE_PROMPTS_DIR",str(capture))
    env = {"CLAUDE_CONFIG_DIR":str(config),"CLAUDE_PROMPTS_DIR":str(capture),owner.PROVIDER_AUTH_SECRET_ENV_KEYS_V1["claude-direct"][0]:"synthetic credential before rotation"}
    mutable = {"mode":mode,"extra":{}}
    def resolve(provider, source):
        assert provider == "claude"
        return SimpleNamespace(mode=mutable["mode"],child_environment={**source,**mutable["extra"]})
    monkeypatch.setattr(owner,"resolve_provider_auth_configuration",resolve)
    monkeypatch.setattr(owner,"_qualify_managed_model_launch",lambda *args,**kwargs:None)
    return selected,path,env,mutable


def prepare(tmp_path,monkeypatch,**kwargs):
    selected,path,env,mutable=fixture(tmp_path,monkeypatch,**kwargs)
    operation=dispatch.prepare_dispatch(selected,path,provider="claude",source_environment=env,cancellation_probe=lambda:False)
    return operation,env,mutable


def test_prompt_only_selection_has_no_filesystem_capability_or_account_identity_claim(tmp_path,monkeypatch):
    op,env,_=prepare(tmp_path,monkeypatch)
    assert op.request.provider == "claude" and op.request.role == "consultant"
    assert op.request.result_kind == "task" and op.request.tool_profile == "prompt-only"
    assert op.request.write_workspace is None
    assert op.selection.instructions == owner.assemble_external_prompt(b"").decode()
    assert op.request.prompt == "Review fixture source only."
    assert not (Path(op.selection.work_item)/"agent-runs.jsonl").exists()
    env["ANTHROPIC_API_KEY"]="changed caller dictionary"
    op._consumed=True
    for stage in dispatch._CLAUDE_STAGES[:6]: op.assert_current(op.request,stage)
    assert op._verify_auth_context(op.request,{"phase":"before_connect","data":{}})==op.request.account_binding


@pytest.mark.parametrize("mode",["claude-subscription-override","unknown"])
def test_no_subscription_or_unknown_mode(tmp_path,monkeypatch,mode):
    with pytest.raises(dispatch.DispatchError,match="API_AUTH"):
        prepare(tmp_path,monkeypatch,mode=mode)


def test_model_alias_not_silently_resolved(tmp_path,monkeypatch):
    with pytest.raises(dispatch.DispatchError,match="PROMPT_ONLY"):
        prepare(tmp_path,monkeypatch,model="opus")


def test_stage_sequence_and_exact_output_callback(tmp_path,monkeypatch):
    op,_,_=prepare(tmp_path,monkeypatch)
    op._consumed=True
    for stage in dispatch._CLAUDE_STAGES:
        op.assert_current(op.request,stage)
    data=dict(run_id=op.request.external_evidence_run_id,artifact_id=op.request.artifact_id,role="consultant",content="Advice")
    op.assert_current(op.request,"tool")
    assert op._authorize_tool(op.request,"StructuredOutput",data) is None
    for name in ["Read","Glob","Grep","Write","Bash"]:
        with pytest.raises(dispatch.DispatchError,match="TOOL_DENIED"):
            op._authorize_tool(op.request,name,{})
    with pytest.raises(ValueError): op._authorize_tool(op.request,"StructuredOutput",{**data,"run_id":"wrong"})
    with pytest.raises(dispatch.DispatchError,match="EFFECT_DENIED"): op.assert_current(op.request,"connect")


@pytest.mark.parametrize("change",["mode","credential","request","control"])
def test_auth_context_or_admission_drift_is_not_cached(tmp_path,monkeypatch,change):
    op,_,mutable=prepare(tmp_path,monkeypatch)
    op._consumed=True
    req=op.request
    if change=="mode":mutable["mode"]="claude-vertex"
    elif change=="credential":mutable["extra"]={owner.PROVIDER_AUTH_SECRET_ENV_KEYS_V1["claude-direct"][0]:"synthetic credential after rotation"}
    elif change=="request":req=replace(req,scope=("different",))
    else:op.prevalidated.control.ledger_role="qa-engineer"
    with pytest.raises(dispatch.DispatchError):op.assert_current(req,"sdk_prepare")


def test_shared_execute_passes_real_provider_callbacks_without_invoking_model(tmp_path,monkeypatch):
    op,_,_=prepare(tmp_path,monkeypatch)
    seen=[]
    def fake(req,selected,**kwargs):
        seen.append((req,selected,kwargs))
        return SimpleNamespace()
    monkeypatch.setattr(runtime,"run_admitted_review",fake)
    result=op.execute(object())
    assert result is op.runtime_run and len(seen)==1
    assert seen[0][2]["authorize_tool"]==op._authorize_tool
    assert seen[0][2]["verify_account"]==op._verify_auth_context
    with pytest.raises(dispatch.DispatchError,match="CONSUMED"):op.execute(object())


@pytest.mark.parametrize("field,value",[("expectedAccountEmail","identity@example.invalid"),("writeWorkspace","workspace")])
def test_codex_specific_binding_does_not_gain_claude_permissions(tmp_path,monkeypatch,field,value):
    selected,path,env,_=fixture(tmp_path,monkeypatch)
    data=binding()
    if field=="writeWorkspace":
        data.update(schemaVersion=4,installedHookRoot=None,contextMode="fresh",contextHandoff=None,writeWorkspace=str(tmp_path))
    else:data[field]=value
    path.write_text(json.dumps(data))
    with pytest.raises(dispatch.DispatchError):
        dispatch.prepare_dispatch(selected,path,provider="claude",source_environment=env,cancellation_probe=lambda:False)


def test_cli_selector_reaches_same_dispatch_before_receipt(tmp_path,monkeypatch):
    fixture(tmp_path,monkeypatch)
    class Reached(Exception):pass
    def prepare(selected,path,**kwargs):
        assert kwargs["provider"]=="claude"
        assert selected.role_provenance.execution_role=="consultant"
        raise Reached()
    monkeypatch.setattr(dispatch,"prepare_dispatch",prepare)
    monkeypatch.setattr(owner.TerminalReceiptV1,"reserve",lambda *args:pytest.fail("premature receipt"))
    with pytest.raises(Reached):
        owner.launch("claude",["advice","--sdk-task-binding","binding.json","--terminal-receipt","receipt.json","--ledger-role","consultant","--","-p","--output-format","text","--model","claude-opus-4-7","--effort","high"])


def test_real_adapter_callback_order_with_output_tool_is_admitted(tmp_path,monkeypatch):
    import asyncio
    import test_sdk_claude_consultant as adapter_fixture
    import test_sdk_claude as native
    op,_,_=prepare(tmp_path,monkeypatch)
    op._consumed=True
    for effect in dispatch._CLAUDE_STAGES[:4]:op.assert_current(op.request,effect)
    client=native.FakeClient()
    client.init_change["tools"]=[native.OUTPUT_TOOL]
    data=dict(run_id=op.request.external_evidence_run_id,artifact_id=op.request.artifact_id,role="consultant",content="Advice")
    client.terminal_change["structured_output"]=data
    def verify(req,evidence):
        op.assert_current(req,"account")
        return op._verify_auth_context(req,evidence)
    def authorize(req,name,args):
        op.assert_current(req,"tool")
        return op._authorize_tool(req,name,args)
    async def output():
        change=dict(tool_name=native.OUTPUT_TOOL,tool_input=data)
        decision=await client.hook("PreToolUse",**change)
        assert decision["hookSpecificOutput"]["permissionDecision"]=="allow"
        await client.hook("PostToolUse",**change)
    client.before_terminal=output
    instance,_=adapter_fixture.adapter(monkeypatch,client,authority=op.assert_current,
        authorize=authorize,verify=verify,instructions=lambda req:op.selection.instructions)
    result=asyncio.run(instance.execute(op.request))
    assert result.status=="completed" and result.task is not None and result.review is None
    assert client.options["tools"]==[]
    with pytest.raises(dispatch.DispatchError,match="AUTH_CONTEXT_INVALID"):
        op._verify_auth_context(op.request,{"phase":"before_connect","data":{}})


def test_cli_operation_real_runtime_claim_and_receiving_without_native_process(tmp_path,monkeypatch):
    import process_supervision.sdk_worker as worker
    from process_supervision.process_runner import ProcessRunnerV1
    import test_sdk_claude_consultant_receiving as receiving_fixture
    op,_,_=prepare(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,"prepare_environment",lambda *args:({},owner.ProviderOutputContext(())))
    calls=[]
    def simulated(process,req,**kwargs):
        calls.append(req)
        for effect in dispatch._CLAUDE_STAGES[4:]:
            if effect=="account":
                phase={5:"before_connect",7:"initialize",9:"system_init"}[op._stage]
                kwargs["authority"](req,effect,{"kind":"account","evidence":{"phase":phase,"data":{}}})
            else:kwargs["authority"](req,effect)
        selected=runtime.runtime_selection_from_dict("claude",kwargs["runtime_selection"])
        return receiving_fixture.observed(monkeypatch,req,selected)
    monkeypatch.setattr(worker,"run_sdk_worker",simulated)
    with ProcessRunnerV1() as process:
        op.execute(process)
    received=op.receive()
    assert received.exit_code==0 and received.terminal["gate"]=="none"
    assert received.terminal["executionRole"]=="consultant" and received.terminal["authorizing"] is False
    assert len(calls)==1
    with pytest.raises(dispatch.DispatchError):op.execute(object())
    with pytest.raises(dispatch.DispatchError):op.receive()


def test_no_explicit_ledger_caps_does_not_invent_limits(tmp_path,monkeypatch):
    selected,path,env,_=fixture(tmp_path,monkeypatch)
    selected.control.ledger_max_events=selected.control.ledger_max_bytes=None
    op=dispatch.prepare_dispatch(selected,path,provider="claude",source_environment=env,cancellation_probe=lambda:False)
    assert op.selection.ledger_max_events is op.selection.ledger_max_bytes is None


@pytest.mark.parametrize("extra", [
    ["--tools","Read"], ["--disallowedTools","StructuredOutput"],
    ["--allowedTools","Read"], ["--permission-mode","bypassPermissions"],
    ["--input-format","stream-json"], ["--output-format","json"],
    ["--setting-sources","user"],
])
def test_unsupported_caller_cli_semantics_never_silently_disappear(tmp_path,monkeypatch,extra):
    selected,path,env,_=fixture(tmp_path,monkeypatch)
    selected.control.provider_flags.extend(extra)
    with pytest.raises(ValueError):
        dispatch.prepare_dispatch(selected,path,provider="claude",source_environment=env,cancellation_probe=lambda:False)
    assert not (Path(selected.control.ledger)/"agent-runs.jsonl").exists()

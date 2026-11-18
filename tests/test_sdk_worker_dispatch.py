"""Offline public Worker binding and dispatch; synthetic runtime only."""
import hashlib
import json
from pathlib import Path
import types
import pytest
from test_sdk_dispatch import fixture, binding, owner, dispatch, runtime


def worker_fixture(tmp_path, monkeypatch, *, role="backend-engineer"):
    selected,path,environment=fixture(tmp_path,monkeypatch,ledger_role=role)
    workspace=tmp_path/"workspace"
    workspace.mkdir()
    install=tmp_path/"install"
    install.mkdir()
    executable=install/"fixture.exe"
    executable.write_bytes(b"never execute")
    monkeypatch.setattr(owner,"_resolve_launch_provider_command",lambda *a:([str(executable)],None))
    authority=tmp_path/"authority"
    authority.mkdir()
    monkeypatch.setattr(runtime,"_worker_authority_roots",lambda:(authority,))
    capture=tmp_path/"capture"
    capture.mkdir()
    environment["CODEX_PROMPTS_DIR"]=str(capture)
    monkeypatch.setenv("CODEX_PROMPTS_DIR",str(capture))
    monkeypatch.chdir(workspace)
    selected.control.sdk_task_binding=path
    data=dict(binding(),schemaVersion=4,installedHookRoot=None,contextMode="fresh",
              contextHandoff=None,writeWorkspace=str(workspace))
    path.write_text(json.dumps(data))
    return selected,path,environment,data,capture


def prepare_worker(tmp_path,monkeypatch,**kwargs):
    selected,path,environment,data,capture=worker_fixture(tmp_path,monkeypatch,**kwargs)
    operation=dispatch.prepare_dispatch(selected,path,source_environment=environment,cancellation_probe=lambda:False)
    return operation,data,capture


def test_worker_public_prepare_keeps_explicit_scope_and_hash(tmp_path,monkeypatch):
    operation,data,capture=prepare_worker(tmp_path,monkeypatch)
    req=operation.request
    assert req.result_kind=="task" and req.role=="backend-engineer"
    assert req.write_workspace==req.cwd==data["writeWorkspace"]
    assert runtime.execution_role(req)=="external-worker"
    selected=runtime.selected_sdk_execution(req,operation.selection)
    assert selected["sandboxMode"]=="workspace-write"
    assert selected["writeWorkspaceSha256"]==hashlib.sha256(req.write_workspace.encode()).hexdigest()
    assert "writeWorkspace" not in selected
    assert not (Path(operation.selection.work_item)/"agent-runs.jsonl").exists()


@pytest.mark.parametrize("role",["consultant","qa-engineer"])
def test_write_binding_cannot_be_readonly_role(tmp_path,monkeypatch,role):
    selected,path,environment,data,capture=worker_fixture(tmp_path,monkeypatch,role=role)
    with pytest.raises(ValueError):
        dispatch.prepare_dispatch(selected,path,source_environment=environment,cancellation_probe=lambda:False)


@pytest.mark.parametrize("version",[1,2,3])
def test_old_binding_never_infers_worker_permission(tmp_path,monkeypatch,version):
    selected,path,environment,data,capture=worker_fixture(tmp_path,monkeypatch)
    data=binding()
    data["schemaVersion"]=version
    if version>=2:data["installedHookRoot"]=str(tmp_path/"authority")
    if version==3:data.update(contextMode="fresh",contextHandoff=None)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        dispatch.prepare_dispatch(selected,path,source_environment=environment,cancellation_probe=lambda:False)


@pytest.mark.parametrize("change",[{"writeWorkspace":"relative"},{"writeWorkspace":None},
                                  {"contextMode":"fresh","contextHandoff":"unexpected"},{"unknown":True}])
def test_closed_write_binding_rejects_invalid_fields(tmp_path,monkeypatch,change):
    selected,path,environment,data,capture=worker_fixture(tmp_path,monkeypatch)
    data.update(change)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        dispatch.prepare_dispatch(selected,path,source_environment=environment,cancellation_probe=lambda:False)


def test_missing_root_and_different_cwd_rejected(tmp_path,monkeypatch):
    selected,path,environment,data,capture=worker_fixture(tmp_path,monkeypatch)
    data.pop("writeWorkspace")
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): dispatch.read_binding(path)
    data["writeWorkspace"]=str(tmp_path/"other")
    (tmp_path/"other").mkdir()
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        dispatch.prepare_dispatch(selected,path,source_environment=environment,cancellation_probe=lambda:False)


def test_review_selector_cannot_admit_write_binding(tmp_path,monkeypatch):
    selected,path,environment,data,capture=worker_fixture(tmp_path,monkeypatch)
    selected.control.sdk_task_binding=None
    selected.control.sdk_review_binding=path
    with pytest.raises(ValueError):
        dispatch.prepare_dispatch(selected,path,source_environment=environment,cancellation_probe=lambda:False)


def test_capture_directory_required_outside_workspace(tmp_path,monkeypatch):
    selected,path,environment,data,capture=worker_fixture(tmp_path,monkeypatch)
    environment.pop("CODEX_PROMPTS_DIR")
    monkeypatch.delenv("CODEX_PROMPTS_DIR")
    with pytest.raises(ValueError):
        dispatch.prepare_dispatch(selected,path,source_environment=environment,cancellation_probe=lambda:False)


def test_worker_execute_needs_bound_capture_child(tmp_path,monkeypatch):
    operation,data,capture=prepare_worker(tmp_path,monkeypatch)
    calls=[]
    monkeypatch.setattr(runtime,"run_admitted_codex",lambda *a,**k:calls.append(a))
    with pytest.raises(ValueError): operation.execute(object())
    assert calls==[]


def test_capture_binding_cannot_escape_frozen_root(tmp_path,monkeypatch):
    operation,data,capture=prepare_worker(tmp_path,monkeypatch)
    outside=tmp_path/"outside"
    outside.mkdir()
    with pytest.raises(ValueError): operation.bind_capture_directory(outside)


def test_worker_dispatch_calls_existing_runtime_with_bound_capture(tmp_path,monkeypatch):
    operation,data,capture=prepare_worker(tmp_path,monkeypatch)
    run_dir=capture/"run"
    run_dir.mkdir()
    operation.bind_capture_directory(run_dir)
    result=types.SimpleNamespace(observation=object())
    calls=[]
    def fake_runtime(req,selection,**kwargs):
        calls.append((req,selection,kwargs))
        return result
    monkeypatch.setattr(runtime,"run_admitted_codex",fake_runtime)
    assert operation.execute(object()) is result
    assert len(calls)==1 and calls[0][0] is operation.request
    with pytest.raises(ValueError): operation.execute(object())


@pytest.mark.parametrize("sandbox",["workspace-write","read-only","danger-full-access"])
def test_explicit_sandbox_flags_match_worker_mode(tmp_path,monkeypatch,sandbox):
    from dataclasses import replace
    selected,path,environment,data,capture=worker_fixture(tmp_path,monkeypatch)
    selected.control.provider_flags=[*selected.flags,"--sandbox",sandbox]
    flags,model,effort=owner.resolved_profile("codex",selected.control.provider_flags)
    selected=replace(selected,flags=tuple(flags),model=model,effort=effort)
    if sandbox=="workspace-write":
        operation=dispatch.prepare_dispatch(selected,path,source_environment=environment,cancellation_probe=lambda:False)
        assert operation.request.write_workspace==data["writeWorkspace"]
    else:
        with pytest.raises(ValueError):
            dispatch.prepare_dispatch(selected,path,source_environment=environment,cancellation_probe=lambda:False)


def test_changed_capture_selection_stops_before_runtime(tmp_path,monkeypatch):
    operation,data,capture=prepare_worker(tmp_path,monkeypatch)
    run_dir=capture/"run"
    run_dir.mkdir()
    operation.bind_capture_directory(run_dir)
    other=tmp_path/"other-capture"
    other.mkdir()
    monkeypatch.setenv("CODEX_PROMPTS_DIR",str(other))
    monkeypatch.setattr(runtime,"run_admitted_codex",lambda *a,**k:pytest.fail("runtime on changed capture"))
    with pytest.raises(ValueError): operation.execute(object())


def policy_namespace(root):
    namespace=root/"namespace"
    (namespace/"model_routing").mkdir(parents=True)
    (namespace/"model_routing"/"launch_policy.py").write_text("# inert custody fixture\n")
    return namespace


def test_policy_custody_rejects_logical_namespace_in_workspace(tmp_path):
    workspace=tmp_path/"workspace"
    workspace.mkdir()
    namespace=policy_namespace(workspace)
    with pytest.raises(dispatch.DispatchError,match="WRITE_POLICY_CUSTODY"):
        dispatch._require_policy_custody(workspace,namespace)


def test_policy_custody_accepts_ordinary_outside_namespace(tmp_path):
    workspace=tmp_path/"workspace"
    workspace.mkdir()
    namespace=policy_namespace(tmp_path)
    dispatch._require_policy_custody(workspace,namespace)


def test_policy_custody_rejects_outside_symlink_into_workspace(tmp_path):
    from test_sdk_ledger import create_fixture_symlink
    workspace=tmp_path/"workspace"
    workspace.mkdir()
    target=workspace/"launch_policy.py"
    target.write_text("# inert, never imported\n")
    namespace=tmp_path/"namespace"
    (namespace/"model_routing").mkdir(parents=True)
    create_fixture_symlink(namespace/"model_routing"/"launch_policy.py",target)
    with pytest.raises(dispatch.DispatchError,match="WRITE_POLICY_CUSTODY"):
        dispatch._require_policy_custody(workspace,namespace)


def test_public_cli_worker_selector_reaches_dispatch_after_policy(monkeypatch):
    class ReachedDispatch(Exception):
        pass
    def prepare(prevalidated,binding,**kwargs):
        assert prevalidated.role_provenance.execution_role=="external-worker"
        assert prevalidated.role_provenance.assigned_role=="backend-engineer"
        assert binding==Path("worker.json")
        raise ReachedDispatch()
    monkeypatch.setattr(dispatch,"prepare_dispatch",prepare)
    monkeypatch.setattr(owner.TerminalReceiptV1,"reserve",lambda *a:pytest.fail("receipt before dispatch"))
    with pytest.raises(ReachedDispatch):
        owner.launch("codex",["implement","--sdk-task-binding","worker.json",
            "--terminal-receipt","receipt.json","--ledger-role","backend-engineer","--",
            "--model","gpt-6.2-sol","-c","model_reasoning_effort=xhigh"])


@pytest.mark.parametrize("chain", ["intermediate-directory", "file-link-target", "extended-prefix-target"])
def test_policy_custody_detects_intermediate_writable_link_participant(tmp_path,monkeypatch,chain):
    """Simulated resolution topology only, not a native Windows symlink proof."""
    import os
    import stat
    workspace=tmp_path/"workspace"
    workspace.mkdir()
    namespace=policy_namespace(tmp_path)
    selected=namespace/"model_routing"/"launch_policy.py"
    trusted=tmp_path/"trusted.py"
    trusted.write_text("# inert trusted target\n")
    pivot=workspace/"pivot"
    pivot.write_text("# synthetic intermediate\n")
    original_resolve=Path.resolve
    original_lstat=Path.lstat
    original_readlink=os.readlink
    if chain=="intermediate-directory":
        linked=selected.parent
        resolved_map={selected:trusted,linked:workspace}
        targets={linked:workspace}
    else:
        linked=selected
        resolved_map={selected:trusted,pivot:trusted}
        targets={selected:pivot,pivot:trusted}
        if chain == "extended-prefix-target":
            if os.name != "nt":
                pytest.skip("Windows extended-prefix path semantics")
            extended = Path("\\\\?\\" + str(pivot))
            resolved_map[extended] = trusted
            targets = {selected:extended, extended:trusted}
    def resolve(path,*args,**kwargs):
        if path in resolved_map:
            return resolved_map[path]
        return original_resolve(path,*args,**kwargs)
    def lstat(path,*args,**kwargs):
        if path in targets:
            return types.SimpleNamespace(st_mode=stat.S_IFLNK,st_file_attributes=0)
        return original_lstat(path,*args,**kwargs)
    def readlink(path,*args,**kwargs):
        value=Path(path)
        if value in targets:
            return str(targets[value])
        return original_readlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,"resolve",resolve)
    monkeypatch.setattr(Path,"lstat",lstat)
    monkeypatch.setattr(os,"readlink",readlink)
    with pytest.raises(dispatch.DispatchError,match="WRITE_POLICY_CUSTODY"):
        dispatch._require_policy_custody(workspace,namespace)


@pytest.mark.parametrize("plain,extended", [
    (r"D:\workspace\task", r"\\?\D:\workspace\task"),
    (r"\\server\share\workspace", r"\\?\UNC\server\share\workspace"),
])
def test_windows_policy_comparison_normalizes_extended_prefix_only(plain,extended):
    import os
    if os.name != "nt":
        pytest.skip("Windows extended-prefix path semantics")
    assert dispatch._policy_comparison_path(Path(plain)) == dispatch._policy_comparison_path(Path(extended))
    assert dispatch._policy_comparison_path(Path(plain.upper())) == dispatch._policy_comparison_path(Path(plain))

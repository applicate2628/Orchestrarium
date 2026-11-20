"""Worker runtime custody checks with isolated authority roots; no model launch."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest
import hashlib
from test_sdk_runtime import fixture
from sdk_execution import runtime


def worker_fixture(tmp_path, monkeypatch):
    req, selection = fixture(tmp_path)
    binary_root = tmp_path / "vendor-runtime"
    binary_root.mkdir()
    binary = binary_root / "fixture.exe"
    Path(selection.executable).rename(binary)
    workspace = tmp_path / "task-workspace"
    workspace.mkdir()
    authorities = tmp_path / "authority-installation"
    authorities.mkdir()
    # Test basetemp lives under the source checkout. Production roots are NOT
    # configurable; simulate a separately installed authority in this fixture.
    monkeypatch.setattr(runtime, "_worker_authority_roots", lambda: (authorities,))
    selection = replace(selection, executable=str(binary))
    req = runtime.prepare_codex_request(replace(req, role="backend-engineer", result_kind="task",
        cwd=str(workspace), write_workspace=str(workspace)))
    return req, selection, authorities


def test_worker_custody_and_selected_contract(tmp_path,monkeypatch):
    req,sel,_=worker_fixture(tmp_path,monkeypatch)
    identity=runtime.validate_worker_custody(req,sel)
    assert runtime.validate_worker_custody(req,sel,expected_identity=identity)==identity
    runtime.validate_admitted_request(req,sel)
    profile=runtime.selected_sdk_execution(req,sel)
    assert profile["writeWorkspaceSha256"]==hashlib.sha256(req.cwd.encode("utf-8")).hexdigest()
    assert profile["sandboxMode"]=="workspace-write"
    assert runtime.execution_role(req)=="external-worker"
    args=runtime.build_launch_arguments(req,sel,started_at="2026-11-18T00:00:00Z")
    assert args[args.index("--execution-role")+1]=="external-worker"


@pytest.mark.parametrize("kind",["work_item","codex_home","executable","installed_hook_root","authority"])
def test_worker_cannot_write_authority_or_state_subtree(tmp_path,monkeypatch,kind):
    req,sel,authority=worker_fixture(tmp_path,monkeypatch)
    root=Path(req.cwd)
    inside=root/"protected"
    inside.mkdir()
    if kind=="authority": monkeypatch.setattr(runtime,"_worker_authority_roots",lambda:(inside,))
    elif kind=="executable": sel=replace(sel,executable=str(inside/"runtime.exe"))
    else: sel=replace(sel,**{kind:str(inside)})
    with pytest.raises(runtime.RuntimeBindingError,match="overlaps"):
        runtime.validate_worker_custody(req,sel)


@pytest.mark.parametrize("kind",["work_item","codex_home","installed_hook_root","authority"])
def test_workspace_cannot_live_inside_protected_tree(tmp_path,monkeypatch,kind):
    req,sel,authority=worker_fixture(tmp_path,monkeypatch)
    if kind=="authority": monkeypatch.setattr(runtime,"_worker_authority_roots",lambda:(tmp_path,))
    else: sel=replace(sel,**{kind:str(tmp_path)})
    with pytest.raises(runtime.RuntimeBindingError,match="overlaps"):
        runtime.validate_worker_custody(req,sel)


def test_workspace_replacement_invalidates_retained_identity(tmp_path,monkeypatch):
    req,sel,_=worker_fixture(tmp_path,monkeypatch)
    identity=runtime.validate_worker_custody(req,sel)
    root=Path(req.cwd)
    root.rename(root.with_name("retained-old-workspace"))
    root.mkdir()
    with pytest.raises(runtime.RuntimeBindingError,match="identity_changed"):
        runtime.validate_worker_custody(req,sel,expected_identity=identity)


def test_reparse_rejection_precedes_launch_authority(tmp_path,monkeypatch):
    req,sel,_=worker_fixture(tmp_path,monkeypatch)
    original = runtime._owner().validate_no_reparse_components
    def reject(path):
        if path == Path(req.cwd):
            raise ValueError("synthetic reparse")
        return original(path)
    monkeypatch.setattr(runtime._owner(),"validate_no_reparse_components",reject)
    calls=[]
    with pytest.raises(runtime.RuntimeBindingError,match="custody_unavailable"):
        runtime.claim_launch(req,sel,authority=lambda *a:calls.append(a),started_at="2026-11-18T00:00:00Z")
    assert calls==[]


def test_worker_role_cannot_be_reviewer_or_consultant(tmp_path,monkeypatch):
    req,sel,_=worker_fixture(tmp_path,monkeypatch)
    for role in ("consultant","qa-engineer","lead"):
        with pytest.raises(runtime.RuntimeBindingError,match="worker_role_required"):
            runtime.validate_worker_custody(replace(req,role=role),sel)


def test_read_only_custody_remains_noop(tmp_path):
    req,sel=fixture(tmp_path)
    assert runtime.validate_worker_custody(req,sel) is None
    assert "writeWorkspaceSha256" not in runtime.selected_sdk_execution(req,sel)


def test_worker_factory_selects_adapter_without_constructing_provider(tmp_path,monkeypatch):
    req,sel,_=worker_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,"assert_current_launch",lambda *a:None)
    monkeypatch.setattr(runtime,"prepare_environment",lambda *a:(dict(runtime.os.environ),None))
    sink=SimpleNamespace(record_from_thread=lambda *a:None,authorize_from_thread=lambda *a:None)
    adapter=runtime.create_codex_adapter(req,sink,sel)
    from sdk_execution.codex import CodexWorkerAdapter
    assert type(adapter) is CodexWorkerAdapter

def test_authority_roots_include_loaded_sources_interpreter_and_discovered_sdk(monkeypatch,tmp_path):
    import importlib.util
    origin=tmp_path/"official-package"/"__init__.py"
    calls=[]
    def discover(name):
        calls.append(name)
        return SimpleNamespace(origin=str(origin),submodule_search_locations=[str(origin.parent)])
    monkeypatch.setattr(importlib.util,"find_spec",discover)
    roots=runtime._worker_authority_roots()
    assert origin.parent in roots
    assert Path(runtime.__file__).absolute().parents[2] in roots
    assert Path(runtime.__file__).resolve().parents[2] in roots
    assert Path(runtime.sys.prefix) in roots
    assert Path(runtime.sys.base_prefix) in roots
    assert Path(runtime.sys.executable).parent in roots
    assert calls==["openai_codex"]

def test_observation_retains_preexecution_workspace_identity_and_seals_it(tmp_path,monkeypatch):
    from test_sdk_worker_receiving import observed
    req,sel,_=worker_fixture(tmp_path,monkeypatch)
    original=runtime.validate_worker_custody(req,sel)
    def replace_workspace(process):
        root=Path(req.cwd)
        root.rename(root.with_name("preserved-original-workspace"))
        root.mkdir()
        return process
    observation=observed(monkeypatch,req,sel,alter_process=replace_workspace)
    assert observation.is_bound_to(req)
    assert observation.workspace_identity == original
    current=runtime.validate_worker_custody(req,sel)
    assert current != original
    with pytest.raises(runtime.RuntimeBindingError,match="identity_changed"):
        runtime.validate_worker_custody(req,sel,expected_identity=observation.workspace_identity)
    assert not replace(observation,workspace_identity=current).is_bound_to(req)
    assert not replace(observation,workspace_identity=None).is_bound_to(req)
    assert observation.result is not None  # Keep captured evidence for reconciliation.


def test_worker_without_selection_cannot_create_unpinned_observation(tmp_path,monkeypatch):
    from test_sdk_worker_receiving import observed
    req,sel,_=worker_fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="retained runtime selection"):
        observed(monkeypatch,req,sel,retain=False)

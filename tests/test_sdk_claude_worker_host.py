"""Claude Worker Host integration with synthetic worker transport only."""
import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest
import jsonschema
import test_sdk_claude_executor as host
from sdk_execution import runtime
from test_agent_run_ledger import load_ledger_module


def setup(tmp_path,monkeypatch,**kwargs):
    original=host.fixtures.fixture
    def worker_fixture(root):
        item,req,selection,_=original(root)
        workspace=root/'work';workspace.mkdir()
        install=root/'install';install.mkdir()
        config=root/'config';config.mkdir()
        capture=root/'capture';capture.mkdir()
        executable=install/'claude.exe';executable.write_bytes(b'fixture')
        req=replace(req,role='backend-engineer',cwd=str(workspace.resolve()),write_workspace=str(workspace.resolve()))
        selection=replace(selection,executable=str(executable),config_dir=str(config),prompts_dir=str(capture))
        return item,req,selection,runtime.selected_sdk_execution(req,selection)
    monkeypatch.setattr(host.fixtures,'fixture',worker_fixture)
    monkeypatch.setattr(runtime,'_worker_authority_roots',lambda provider='codex':(tmp_path/'authority',))
    return host.setup(tmp_path,monkeypatch,**kwargs)


def test_host_worker_receives_task_not_review_and_cannot_replay(tmp_path,monkeypatch):
    case=setup(tmp_path,monkeypatch)
    with case.process:
        result=asyncio.run(case.executor.execute(case.req))
        assert result.task is not None and result.review is None
        terminal=case.executor.terminal
        assert terminal['executionRole']=='external-worker' and terminal['gate']=='none'
        assert terminal['authorizing'] is False and terminal['closesRunIds']==[]
        assert terminal['sdkExecution']['sandboxMode']=='tool-restricted-workspace-write'
        assert len(terminal['sdkExecution']['writeWorkspaceSha256'])==64
        with pytest.raises(ValueError):asyncio.run(case.executor.execute(case.req))
    assert len(case.worker_calls)==1


@pytest.mark.parametrize('field',['config_dir','prompts_dir','work_item','executable'])
def test_protected_selected_state_overlap_rejected(tmp_path,monkeypatch,field):
    case=setup(tmp_path,monkeypatch)
    selection=case.executor._selection
    target=str(Path(case.req.cwd)/'nested') if field=='executable' else case.req.cwd
    with case.process,pytest.raises(ValueError,match='overlaps'):
        runtime.validate_worker_custody(case.req,replace(selection,**{field:target}))


def test_original_directory_identity_cannot_be_replaced(tmp_path,monkeypatch):
    case=setup(tmp_path,monkeypatch)
    with case.process:
        identity=runtime.validate_worker_custody(case.req,case.executor._selection)
        root=Path(case.req.cwd);root.rename(root.with_name('old-work'));root.mkdir()
        with pytest.raises(ValueError,match='identity_changed'):
            runtime.validate_worker_custody(case.req,case.executor._selection,expected_identity=identity)


@pytest.mark.parametrize('mode',['claude-subscription-override','unknown'])
def test_worker_api_context_only(tmp_path,monkeypatch,mode):
    case=setup(tmp_path,monkeypatch)
    with case.process,pytest.raises(ValueError,match='programmatic_auth'):
        runtime.validate_admitted_request(case.req,replace(case.executor._selection,auth_mode=mode))


@pytest.mark.parametrize('change',[{}, {'sandboxMode':'tool-restricted-read-only'}, {'sandboxMode':'workspace-write'}, {'writeWorkspaceSha256':'A'*64}])
def test_metadata_python_jsonschema_agree(tmp_path,monkeypatch,change):
    case=setup(tmp_path,monkeypatch)
    with case.process:
        value=runtime.selected_sdk_execution(case.req,case.executor._selection);value.update(change)
        validator=load_ledger_module().load_validator()
        check=lambda:validator.validate_sdk_execution(value,provider='claude',model=case.req.model,effort=case.req.effort)
        schema=lambda:jsonschema.validate(value,validator.AGENT_RUN_SCHEMA['properties']['sdkExecution'])
        if change:
            with pytest.raises(ValueError):check()
            with pytest.raises(jsonschema.ValidationError):schema()
        else:assert check()==value;schema()


def test_custom_claude_sdk_root_discovered_without_import(monkeypatch,tmp_path):
    import importlib.util
    roots=tmp_path/'external-sdk'
    calls=[]
    def find(name):
        calls.append(name);return SimpleNamespace(origin=str(roots/'__init__.py'),submodule_search_locations=[str(roots)])
    monkeypatch.setattr(importlib.util,'find_spec',find)
    assert roots in runtime._worker_authority_roots('claude')
    assert calls==['claude_agent_sdk']


def test_host_tool_denial_no_success_or_replay(tmp_path,monkeypatch):
    case=setup(tmp_path,monkeypatch,denied='tool-owner')
    with case.process,pytest.raises(ValueError):asyncio.run(case.executor.execute(case.req))
    assert len(case.worker_calls)==1 and case.executor.terminal is None


def test_custom_sdk_package_overlap_rejected(tmp_path,monkeypatch):
    case=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,'_worker_authority_roots',lambda provider='codex':(Path(case.req.cwd)/'sdk-package',))
    with case.process,pytest.raises(ValueError,match='overlaps'):
        runtime.validate_worker_custody(case.req,case.executor._selection)


@pytest.mark.parametrize('mode',['tool-restricted-read-only','workspace-write'])
def test_reported_wrong_write_mode_cannot_complete(tmp_path,monkeypatch,mode):
    from sdk_execution.receiving import terminal_payload
    case=setup(tmp_path,monkeypatch)
    with case.process:
        obs=host.fixtures.observed(monkeypatch,case.req,case.executor._selection,config={'sandboxMode':mode})
        result=terminal_payload(case.req,obs,output_context=host.ProviderOutputContext(()),admitted_sdk_execution=runtime.selected_sdk_execution(case.req,case.executor._selection))
        assert result["status"]=="blocked" and result["gate"]=="none"
        assert result["authorizing"] is False


def test_receiving_failure_retains_worker_and_repair_has_no_reexecution(tmp_path,monkeypatch):
    from sdk_execution.receiving import terminal_payload, receive_terminal
    case=setup(tmp_path,monkeypatch,receiving_failure=True)
    with case.process:
        with pytest.raises(ValueError):asyncio.run(case.executor.execute(case.req))
        run=case.executor.runtime_run
        assert run is not None and run.observation.is_bound_to(case.req)
        selected=runtime.selected_sdk_execution(run.request,run.selection)
        payload=terminal_payload(run.request,run.observation,output_context=run.output_context,admitted_sdk_execution=selected)
        (case.item/'executor-result.json').write_bytes((payload['resultText']+'\n').encode())
        result=receive_terminal(case.item,run.request,run.observation,artifact='executor-result.json',started_at='2026-10-23T10:00:00Z',updated_at='2026-10-23T10:01:00Z',ledger_max_events=100,ledger_max_bytes=1048576,output_context=run.output_context)
        assert result['gate']=='none' and result['authorizing'] is False
        with pytest.raises(ValueError):asyncio.run(case.executor.execute(case.req))
        assert len(case.worker_calls)==1

"""Offline Worker adapter contract; no provider client or model is launched."""
import asyncio
import pytest
from test_sdk_codex import request, FakeClient, ClientBinding, answer, successful_events
from sdk_execution.codex import CodexWorkerAdapter, CodexReviewAdapter, CodexConsultantAdapter
from sdk_execution.codex_tools import CodexMcpScope


def workspace_request(tmp_path, **changes):
    root = tmp_path / "workspace"
    root.mkdir(exist_ok=True)
    values = dict(role="backend-engineer", result_kind="task", cwd=str(root),
                  write_workspace=str(root), prompt="Implement the admitted change.")
    values.update(changes)
    return request(**values)


def policy(**changes):
    value = dict(type="workspaceWrite", writableRoots=[], networkAccess=False,
                 excludeTmpdirEnvVar=True, excludeSlashTmp=True)
    value.update(changes)
    return value


def worker(req, *, authority=None, scope=CodexMcpScope(()), adapter_type=CodexWorkerAdapter):
    payload = dict(run_id=req.external_evidence_run_id, artifact_id=req.artifact_id,
                   role=req.role, content="Implemented scoped change; local verification recorded.")
    client = FakeClient(successful_events(answer(payload)))
    client.profile_change = {"cwd":req.cwd, "sandbox":policy()}
    def factory(handler):
        client.handler = handler
        return ClientBinding(client, "fixture-1", client.read_configuration, client.list_mcp_status)
    adapter = adapter_type(client_factory=factory, assert_current=authority or (lambda *a:None),
        verify_account=lambda req,data:req.account_binding, record=lambda obs:None, mcp_scope=scope)
    return adapter, client


@pytest.mark.parametrize("explicit_cwd", [False, True])
def test_worker_success_binds_thread_and_turn_workspace(tmp_path, explicit_cwd):
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    if explicit_cwd:
        client.profile_change["sandbox"]["writableRoots"] = [req.cwd]
    result = asyncio.run(adapter.execute(req))
    assert result.status == "completed" and result.protocol_closed
    assert result.task.role == req.role and result.review is None
    assert result.to_tool_output()["authoritative"] is False
    assert result.sdk_execution["sandboxMode"] == "workspace-write"
    thread = next(call[1] for call in client.calls if call[0] == "thread_start")
    turn = next(call[3] for call in client.calls if call[0] == "turn_start")
    assert thread["sandbox"] == "workspace-write"
    assert thread["cwd"] == turn["cwd"] == req.write_workspace
    assert thread["approvalPolicy"] == turn["approvalPolicy"] == "never"
    for key, value in {"writable_roots":[], "network_access":False,
                       "exclude_tmpdir_env_var":True, "exclude_slash_tmp":True}.items():
        assert thread["config"]["sandbox_workspace_write."+key] == value
    assert turn["sandboxPolicy"] == policy()
    assert "verdict" not in turn["outputSchema"]["properties"]


@pytest.mark.parametrize("change", [
    {"writableRoots":["/unapproved"]}, {"networkAccess":True},
    {"excludeTmpdirEnvVar":False}, {"excludeSlashTmp":False},
    {"excludeTmpdirEnvVar":None}, {"type":"dangerFullAccess"}])
def test_observed_permission_expansion_stops_before_turn(tmp_path, change):
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    client.profile_change["sandbox"] = policy(**change)
    result = asyncio.run(adapter.execute(req))
    assert result.status != "completed" and result.task is None
    assert result.execution_error == "observed_profile_mismatch"
    assert not any(call[0] == "turn_start" for call in client.calls)
    assert result.protocol_closed


@pytest.mark.parametrize("role", ["consultant", "architecture-reviewer", "lead", "unknown-role"])
def test_worker_taxonomy_rejects_nonworkers_before_client(tmp_path, role):
    req = workspace_request(tmp_path, role=role)
    adapter, client = worker(req)
    with pytest.raises(ValueError, match="worker_role_required"):
        asyncio.run(adapter.execute(req))
    assert client.calls == []


@pytest.mark.parametrize("adapter_type", [CodexReviewAdapter, CodexConsultantAdapter])
def test_read_only_adapters_cannot_receive_write_contract(tmp_path, adapter_type):
    req = workspace_request(tmp_path)
    adapter, client = worker(req, adapter_type=adapter_type)
    with pytest.raises(ValueError):
        asyncio.run(adapter.execute(req))
    assert client.calls == []


def test_worker_denies_provider_approval(tmp_path):
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    def approval():
        assert client.handler("item/commandExecution/requestApproval", {}) == {"decision":"cancel"}
    client.on_turn = approval
    result = asyncio.run(adapter.execute(req))
    assert result.status != "completed"
    assert result.execution_error == "unexpected_approval_request"


def test_workspace_replacement_stops_next_effect_without_replay(tmp_path):
    from pathlib import Path
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    def replace_workspace():
        root = Path(req.cwd)
        root.rename(root.with_name("retained-original"))
        root.mkdir()
    client.on_start = replace_workspace
    result = asyncio.run(adapter.execute(req))
    assert result.status != "completed" and result.task is None
    assert result.execution_error == "worker_workspace_changed"
    assert not any(call[0] in {"thread_start", "turn_start"} for call in client.calls)
    assert sum(call[0] == "start" for call in client.calls) == 1
    before = list(client.calls)
    with pytest.raises(ValueError, match="worker_resume_not_qualified"):
        asyncio.run(adapter.reconcile(req, thread_id="thread-1", turn_id="turn-1"))
    assert client.calls == before


def test_worker_authority_refusal_prevents_native_effect(tmp_path):
    req = workspace_request(tmp_path)
    def refuse(*args):
        raise ValueError("fixture authority refused")
    adapter, client = worker(req, authority=refuse)
    result = asyncio.run(adapter.execute(req))
    assert result.status != "completed"
    assert client.calls == []


def test_missing_workspace_is_not_created_by_adapter(tmp_path):
    req = workspace_request(tmp_path)
    from pathlib import Path
    Path(req.cwd).rename(Path(req.cwd).with_name("retained-workspace"))
    adapter, client = worker(req)
    with pytest.raises(ValueError, match="worker_workspace_unavailable"):
        asyncio.run(adapter.execute(req))
    assert not Path(req.cwd).exists() and client.calls == []


def file_change(req, status="completed"):
    from pathlib import Path
    return {"id":"file-1", "type":"fileChange", "status":status,
            "changes":[{"path":str(Path(req.cwd)/"result.txt"), "kind":{"type":"add"}, "diff":"+result"}]}


def test_worker_accepts_completed_file_change_stream(tmp_path):
    from test_sdk_codex import item_completed
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    client.events.insert(0, item_completed(file_change(req)))
    result = asyncio.run(adapter.execute(req))
    assert result.status == "completed" and result.task is not None
    assert result.review is None and result.to_tool_output()["authoritative"] is False


@pytest.mark.parametrize("status", ["inProgress", None])
def test_worker_file_change_failure_never_becomes_completion(tmp_path, status):
    from test_sdk_codex import item_completed
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    item = file_change(req, status)
    if status is None:
        item.pop("status")
    client.events.insert(0, item_completed(item))
    result = asyncio.run(adapter.execute(req))
    assert result.status != "completed" and result.task is None


def test_worker_pending_file_change_is_not_complete(tmp_path):
    from test_sdk_codex import event
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    client.events.insert(0, event("item/started", {"threadId":"thread-1", "turnId":"turn-1",
                                                 "item":file_change(req, "inProgress")}))
    result = asyncio.run(adapter.execute(req))
    assert result.status != "completed" and result.task is None


def test_worker_contradictory_file_change_is_not_complete(tmp_path):
    from test_sdk_codex import item_completed
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    original = file_change(req)
    changed = file_change(req)
    changed["changes"][0]["diff"] = "+contradiction"
    client.events[0:0] = [item_completed(original), item_completed(changed)]
    result = asyncio.run(adapter.execute(req))
    assert result.status != "completed"
    assert result.execution_error == "contradictory_duplicate_item"


def test_worker_runtime_requires_retained_selection_before_composition(tmp_path):
    from sdk_execution.runtime import validate_admitted_request, execution_role, RuntimeBindingError, selected_sdk_execution, create_codex_adapter
    req = workspace_request(tmp_path)
    with pytest.raises(RuntimeBindingError, match="worker_runtime_selection_required"):
        validate_admitted_request(req, None)
    assert execution_role(req) == "external-worker"
    with pytest.raises(RuntimeBindingError, match="worker_runtime_selection_required"):
        selected_sdk_execution(req, None)
    with pytest.raises(RuntimeBindingError, match="worker_runtime_selection_required"):
        create_codex_adapter(req, None, None)


def test_worker_selected_external_tools_rejected_before_client(tmp_path):
    req = workspace_request(tmp_path)
    adapter, client = worker(req, scope=CodexMcpScope((("fixture-server", ("read",)),)))
    with pytest.raises(ValueError, match="worker_external_tools_not_qualified"):
        asyncio.run(adapter.execute(req))
    assert client.calls == []


@pytest.mark.parametrize("malformation", ["missing-kind", "missing-path", "missing-diff",
                                         "outside-path", "outside-move", "missing-move"])
def test_worker_rejects_malformed_or_outside_file_change(tmp_path, malformation):
    from test_sdk_codex import item_completed
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    item = file_change(req)
    change = item["changes"][0]
    if malformation.startswith("missing-") and malformation != "missing-move":
        change.pop(malformation.removeprefix("missing-"))
    elif malformation == "outside-path":
        change["path"] = str(tmp_path / "outside.txt")
    elif malformation == "outside-move":
        change["kind"] = {"type":"update", "move_path":str(tmp_path / "outside.txt")}
    else:
        change["kind"] = {"type":"update"}
    client.events.insert(0, item_completed(item))
    result = asyncio.run(adapter.execute(req))
    assert result.status != "completed" and result.task is None


def test_worker_accepts_update_without_move(tmp_path):
    from test_sdk_codex import item_completed
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    item = file_change(req)
    item["changes"][0]["kind"] = {"type":"update", "move_path":None}
    client.events.insert(0, item_completed(item))
    result = asyncio.run(adapter.execute(req))
    assert result.status == "completed"


@pytest.mark.parametrize("status", ["failed", "declined"])
def test_worker_retains_recoverable_patch_failure_as_nonauthorizing_evidence(tmp_path, status):
    from test_sdk_codex import item_completed
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    failed = file_change(req, status)
    corrected = file_change(req)
    corrected["id"] = "corrected-patch"
    client.events[0:0] = [item_completed(failed), item_completed(corrected)]
    result = asyncio.run(adapter.execute(req))
    assert result.status == "completed" and result.review is None
    assert result.to_tool_output()["authoritative"] is False
    assert any(status in observation.payload_json for observation in result.observations)


def test_worker_failed_turn_cannot_become_task_completion(tmp_path):
    from test_sdk_codex import item_completed, completed
    req = workspace_request(tmp_path)
    adapter, client = worker(req)
    client.events = [item_completed(file_change(req, "failed")), completed("failed", items=[])]
    result = asyncio.run(adapter.execute(req))
    assert result.status == "failed" and result.task is None

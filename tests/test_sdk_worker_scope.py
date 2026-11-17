"""Portable workspace-write value contract; no provider or filesystem effects."""
import inspect
from dataclasses import FrozenInstanceError, replace
import pytest
from test_sdk_codex import request
from sdk_execution.contracts import ExecutionRequest, json_text


def worker_request(**changes):
    data = dict(role="backend-engineer", result_kind="task", cwd=r"D:\work\example\task", write_workspace=r"D:\work\example\task")
    data.update(changes)
    return request(**data)


@pytest.mark.parametrize("workspace", [r"D:\work\example\task", "/work/task"])
def test_explicit_whole_workspace_roundtrips_and_is_immutable(workspace):
    req = worker_request(cwd=workspace, write_workspace=workspace)
    assert ExecutionRequest.from_dict(req.to_dict()) == req
    assert req.to_dict()["write_workspace"] == workspace
    with pytest.raises(FrozenInstanceError):
        req.write_workspace = "/other"
    assert inspect.signature(ExecutionRequest).parameters["write_workspace"].kind is inspect.Parameter.KEYWORD_ONLY


def test_legacy_read_only_requests_keep_exact_wire_shape():
    req = request()
    old = req.to_dict()
    assert "write_workspace" not in old
    assert ExecutionRequest.from_dict(old).to_dict() == old
    consultant = request(role="consultant", result_kind="task")
    assert "write_workspace" not in consultant.to_dict()
    assert ExecutionRequest.from_dict(consultant.to_dict()) == consultant


@pytest.mark.parametrize("workspace", ["relative", "D:relative", r"\rooted", "", " ",
    "D:/work/example/task", "D:\\work\\example\\.\\task", "D:\\work\\example\\task\\..\\other", "D:\\work\\example\\task\\",
    "/work/./task", "/work/../task", "/work//task", "/work/task/", "/work/\0task", 123])
def test_workspace_must_be_normalized_absolute(workspace):
    with pytest.raises(ValueError):
        worker_request(cwd=workspace if isinstance(workspace,str) else r"D:\work\example\task", write_workspace=workspace)


def test_workspace_never_infers_from_text_scope_or_different_cwd():
    with pytest.raises(ValueError):
        worker_request(write_workspace=None, scope=(r"D:\work\example\task",))
    with pytest.raises(ValueError):
        worker_request(cwd=r"D:\work\example\other")
    a=worker_request(scope=("only edit documentation",))
    b=replace(a,scope=("implement feature",))
    assert a.write_workspace == b.write_workspace
    assert json_text(a.to_dict()) != json_text(b.to_dict())


@pytest.mark.parametrize("changes", [{"result_kind":"review"},{"provider":"claude"},{"provider":"grok"}])
def test_write_contract_does_not_expand_other_result_kinds_or_providers(changes):
    with pytest.raises(ValueError):
        worker_request(**changes)


def test_workspace_change_changes_committed_request_representation():
    a=worker_request()
    b=worker_request(cwd=r"D:\work\example\other",write_workspace=r"D:\work\example\other")
    assert json_text(a.to_dict()) != json_text(b.to_dict())

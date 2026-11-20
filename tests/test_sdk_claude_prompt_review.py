"""Offline exact role/auth admission for Claude prompt-only review."""
import pytest
import test_sdk_claude as base
from sdk_execution import runtime
from sdk_execution.contracts import ExecutionRequest
import provider_prompt


def request(**changes):
    return base.request(tool_profile="prompt-only", **changes)


def selection(tmp_path, **changes):
    return base.claude_selection(tmp_path,
        instructions=provider_prompt.assemble_external_prompt(b"Review").decode(), **changes)


@pytest.mark.parametrize("mode", ["claude-direct", "claude-bedrock", "claude-vertex"])
def test_review_admitted_current_auth_and_role(tmp_path, mode):
    req = request()
    selected = selection(tmp_path, auth_mode=mode)
    runtime.validate_admitted_request(req, selected)
    assert runtime.execution_role(req) == "external-reviewer"
    assert runtime.selected_sdk_execution(req, selected)["requestSha256"] == runtime.request_sha256(req, selected)
    assert ExecutionRequest.from_dict(req.to_dict()) == req


@pytest.mark.parametrize("role", ["consultant", "lead", "architect", "unknown"])
def test_nonreview_roles_rejected_by_canonical_owner(tmp_path, role):
    req = request(role=role)
    for call in (lambda: runtime.execution_role(req),
                 lambda: runtime.validate_admitted_request(req, selection(tmp_path)),
                 lambda: runtime.selected_sdk_execution(req, selection(tmp_path))):
        with pytest.raises(runtime.RuntimeBindingError, match="claude_prompt_only_reviewer_required"):
            call()


@pytest.mark.parametrize("mode", ["claude-subscription-override", "unknown"])
def test_review_auth_mode_refused(tmp_path, mode):
    req, selected = request(), selection(tmp_path, auth_mode=mode)
    for call in (lambda: runtime.validate_admitted_request(req, selected),
                 lambda: runtime.selected_sdk_execution(req, selected)):
        with pytest.raises(runtime.RuntimeBindingError, match="claude_programmatic_auth_mode_required"):
            call()


def test_no_write_or_wrong_task_role():
    for change in ({"write_workspace": "/fixture/repo"}, {"result_kind": "task"}):
        with pytest.raises(ValueError):
            request(**change)

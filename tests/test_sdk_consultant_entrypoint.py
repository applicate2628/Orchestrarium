"""Offline public Consultant selector and nonauthorizing receipt boundaries."""
from pathlib import Path
import inspect
import pytest
from test_sdk_provider_result import owner, payload, encode


def consultant_payload():
    data = payload()
    data.update(assignedRole="consultant", executionRole="consultant", gate="none")
    data["primaryOutcome"]["gate"] = "none"
    return data


def test_task_selector_is_explicit_and_preserves_control_positional_api():
    module = owner()
    result = module.parse_control(["advice", "--sdk-task-binding", "task.json", "--", "--model", "fixture"], provider="codex")
    assert result.sdk_task_binding == Path("task.json") and result.sdk_review_binding is None
    assert result.provider_flags == ["--model", "fixture"]
    assert inspect.signature(module.Control).parameters["sdk_task_binding"].kind is inspect.Parameter.KEYWORD_ONLY
    assert module.parse_control(["advice"], provider="codex").sdk_task_binding is None


@pytest.mark.parametrize("provider", [None, "claude", "kimi", "grok"])
def test_task_selector_rejects_unsupported_provider(provider):
    with pytest.raises(ValueError, match="E_SDK_TASK_PROVIDER_REQUIRED"):
        owner().parse_control(["advice", "--sdk-task-binding", "task.json"], provider=provider)


def test_conflicting_result_kind_selectors_are_rejected():
    with pytest.raises(ValueError, match="E_SDK_BINDING_KIND_CONFLICT"):
        owner().parse_control(["advice", "--sdk-task-binding", "a", "--sdk-review-binding", "a"], provider="codex")
    with pytest.raises(ValueError, match="conflicting"):
        owner().parse_control(["advice", "--sdk-task-binding", "a", "--sdk-task-binding", "b"], provider="codex")


@pytest.mark.parametrize("status", ["completed", "blocked"])
def test_consultant_receipt_roundtrip_without_verdict(status):
    module = owner()
    data = consultant_payload()
    data["status"] = data["primaryOutcome"]["status"] = status
    if status != "completed":
        data["token"] = data["primaryOutcome"]["token"] = "UNVERIFIED:E_SDK_EXECUTION_INCOMPLETE"
    assert module.parse_provider_result(encode(module, data)) == data


@pytest.mark.parametrize("change", [
    {"assignedRole":"qa-engineer"}, {"executionRole":"external-worker"},
    {"provider":"claude"}, {"gate":"PASS"}, {"status":"revise"},
    {"token":"COMPLETE:PASS"}, {"authorizing":True}, {"closesRunIds":["other"]},
    {"primaryOutcome":{"gate":"PASS","status":"completed","token":"COMPLETE:PASS"}},
])
def test_consultant_receipt_cannot_become_review_or_authority(change):
    module = owner()
    data = consultant_payload()
    data.update(change)
    with pytest.raises(ValueError):
        module.parse_provider_result(encode(module, data))


def test_task_launch_enters_existing_dispatch_after_policy(monkeypatch):
    from sdk_execution import dispatch
    module = owner()
    class ReachedDispatch(Exception):
        pass
    def prepare(prevalidated, binding, **kwargs):
        assert prevalidated.role_provenance.execution_role == "consultant"
        assert binding == Path("task.json")
        raise ReachedDispatch()
    monkeypatch.setattr(dispatch, "prepare_dispatch", prepare)
    monkeypatch.setattr(module.TerminalReceiptV1, "reserve", lambda *a: pytest.fail("receipt before dispatch"))
    with pytest.raises(ReachedDispatch):
        module.launch("codex", ["advice", "--sdk-task-binding", "task.json", "--terminal-receipt", "receipt.json",
            "--ledger-role", "consultant", "--", "--model", "gpt-6.1-terra", "-c", "model_reasoning_effort=high"])

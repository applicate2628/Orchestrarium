"""Offline Worker custody/receiving integration; no provider or native sandbox run."""
from dataclasses import replace
from pathlib import Path
import json
import hashlib
import pytest
import test_sdk_receiving as receiving_fixtures
from test_sdk_runtime import fixture as runtime_fixture, claim
from sdk_execution import runtime, receiving
from sdk_execution.contracts import ExecutionResult, TaskResult
from provider_prompt import ProviderOutputContext, parse_provider_result, SDK_RESULT_PREFIX
from sdk_execution.contracts import json_text
from test_sdk_ledger import SDK_CONFIG


def fixture(tmp_path, monkeypatch):
    request, selection = runtime_fixture(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    installation = tmp_path / "native-install"
    installation.mkdir()
    executable = installation / "runtime.exe"
    Path(selection.executable).rename(executable)
    selection = replace(selection, executable=str(executable))
    trusted = tmp_path / "trusted-host"
    trusted.mkdir()
    # Test basetemp sits in the source checkout. Model its authority tree as a
    # separate fixture; all real workspace/home/ledger/runtime checks still run.
    monkeypatch.setattr(runtime, "_worker_authority_roots", lambda: (trusted,))
    request = runtime.prepare_codex_request(replace(request, role="backend-engineer", result_kind="task",
        cwd=str(workspace), write_workspace=str(workspace)))
    return request, selection


def observed(monkeypatch, request, selection, *, reported=None, alter_process=None, retain=True):
    if reported is None:
        reported = {**SDK_CONFIG, "model": request.model, "effort": request.effort,
            "accountBinding": request.account_binding, "sandboxMode":"workspace-write",
            "writeWorkspaceSha256": hashlib.sha256(request.write_workspace.encode()).hexdigest()}
    def task_result(**values):
        values.pop("review")
        return ExecutionResult(task=TaskResult(request.external_evidence_run_id, request.artifact_id,
            request.role, "Implementation evidence requires independent validation."), **values)
    with monkeypatch.context() as patch:
        patch.setattr(receiving_fixtures, "ExecutionResult", task_result)
        return receiving_fixtures.synthetic_observation(patch, request,
            runtime_selection=selection.to_dict() if retain else None,
            sdk_config=reported, alter_process=alter_process)


def test_worker_real_ledger_receiving_replays_without_execution(tmp_path, monkeypatch):
    request, selection = fixture(tmp_path, monkeypatch)
    admitted = claim(request, selection)
    observation = observed(monkeypatch, request, admitted)
    selected = runtime.selected_sdk_execution(request, admitted)
    payload = receiving.terminal_payload(request, observation, output_context=ProviderOutputContext(()),
        admitted_sdk_execution=selected)
    parsed = parse_provider_result(SDK_RESULT_PREFIX + json_text(payload) + "\n")
    assert parsed["executionRole"] == "external-worker"
    assert parsed["status"] == "completed" and parsed["gate"] == "none"
    assert parsed["authorizing"] is False and parsed["closesRunIds"] == []
    assert json.loads(parsed["resultText"])["task"] == observation.result.task.to_dict()
    run = runtime.RuntimeRun(request, admitted, ProviderOutputContext(()), observation)
    terminal = receiving.receive_runtime_run(run, artifact="reviews/worker.json",
        started_at="2026-10-23T10:00:00Z", updated_at="2026-10-23T10:01:00Z")
    ledger = Path(selection.work_item) / "agent-runs.jsonl"
    before = ledger.read_bytes()
    assert receiving.receive_terminal(Path(selection.work_item), request, observation, artifact="reviews/worker.json",
        started_at="2026-10-23T10:00:00Z", updated_at="2026-10-23T10:01:00Z",
        ledger_max_events=100, ledger_max_bytes=1048576, output_context=run.output_context) == terminal
    assert ledger.read_bytes() == before


@pytest.mark.parametrize("change", ["unadmitted", "no-retained-selection", "changed-root", "changed-request"])
def test_write_evidence_requires_exact_selected_commitment(tmp_path, monkeypatch, change):
    request, selection = fixture(tmp_path, monkeypatch)
    selected = runtime.selected_sdk_execution(request, selection)
    evidence_request = replace(request, scope=("changed",)) if change == "changed-request" else request
    if change == "no-retained-selection":
        with pytest.raises(ValueError):
            observed(monkeypatch, evidence_request, selection, retain=False)
        return
    observation = observed(monkeypatch, evidence_request, selection)
    if change == "changed-root": selected = {**selected, "writeWorkspaceSha256": "f" * 64}
    with pytest.raises(ValueError):
        receiving.terminal_payload(evidence_request, observation, output_context=ProviderOutputContext(()),
            admitted_sdk_execution=None if change == "unadmitted" else selected)


def test_mismatched_observed_write_workspace_is_blocked_not_accepted(tmp_path, monkeypatch):
    request, selection = fixture(tmp_path, monkeypatch)
    reported = {**SDK_CONFIG,"model":request.model,"effort":request.effort,
        "accountBinding":request.account_binding,"sandboxMode":"workspace-write","writeWorkspaceSha256":"f" * 64}
    observation = observed(monkeypatch, request, selection, reported=reported)
    payload = receiving.terminal_payload(request, observation, output_context=ProviderOutputContext(()),
        admitted_sdk_execution=runtime.selected_sdk_execution(request, selection))
    assert payload["status"] == "blocked" and payload["gate"] == "none"


def test_failed_worker_process_stores_only_blocked_evidence(tmp_path, monkeypatch):
    request, selection = fixture(tmp_path, monkeypatch)
    observation = observed(monkeypatch, request, selection, alter_process=lambda p:replace(p,target_exit_code=1))
    payload = receiving.terminal_payload(request, observation, output_context=ProviderOutputContext(()),
        admitted_sdk_execution=runtime.selected_sdk_execution(request, selection))
    assert payload["status"] == "blocked" and payload["closesRunIds"] == []


@pytest.mark.parametrize("role", ["consultant", "external-reviewer"])
def test_worker_receipt_cannot_be_relabelled_as_review_or_advice(tmp_path, monkeypatch, role):
    request, selection = fixture(tmp_path, monkeypatch)
    payload = receiving.terminal_payload(request, observed(monkeypatch,request,selection),
        output_context=ProviderOutputContext(()), admitted_sdk_execution=runtime.selected_sdk_execution(request,selection))
    payload["executionRole"] = role
    payload["assignedRole"] = "consultant" if role=="consultant" else "qa-engineer"
    with pytest.raises(ValueError):
        parse_provider_result(SDK_RESULT_PREFIX + json_text(payload) + "\n")


def test_workspace_replacement_after_execution_preserves_only_blocked_evidence(tmp_path, monkeypatch):
    request, selection = fixture(tmp_path, monkeypatch)
    observation = observed(monkeypatch, request, selection)
    selected = runtime.selected_sdk_execution(request, selection)
    workspace = Path(request.write_workspace)
    workspace.rename(tmp_path / "retained-original")
    workspace.mkdir()
    payload = receiving.terminal_payload(request, observation, output_context=ProviderOutputContext(()),
        admitted_sdk_execution=selected)
    assert payload["status"] == "blocked" and payload["gate"] == "none"
    assert payload["closesRunIds"] == []

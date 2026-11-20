"""Sealed synthetic Claude task evidence; no vendor process or account calls."""
from dataclasses import replace
import json
import secrets

import pytest
import test_sdk_receiving as base
from test_sdk_claude import claude_selection
from test_sdk_ledger import sdk_launch_args
from test_agent_run_ledger import prepare_valid_work_item, run_ledger, run_validator
from sdk_execution import runtime
from sdk_execution.contracts import ExecutionResult, TaskResult
from sdk_execution.receiving import terminal_payload, receive_terminal
from provider_prompt import ProviderOutputContext, assemble_external_prompt


def fixture(tmp_path, mode="claude-direct"):
    item = prepare_valid_work_item(tmp_path)
    req = replace(base.fixture_request(item), provider="claude", role="consultant", result_kind="task", model="fixture-claude")
    selection = claude_selection(tmp_path, work_item=str(item), auth_mode=mode,
        instructions=assemble_external_prompt(b"Read-only advice.").decode())
    selected = runtime.selected_sdk_execution(req, selection)
    return item, req, selection, selected


def observed(monkeypatch, req, selection, *, retained_selection=None, config=None, process=None, result_changes=None, content="Advice, not authorization."):
    selected = runtime.selected_sdk_execution(req, selection)
    reported = {key:value for key,value in selected.items() if key not in {"schemaVersion", "requestSha256"}}
    reported.update(schemaVersion=1, sdkVersion="fixture-sdk", runtimeVersion="fixture-runtime")
    if config:
        reported.update(config)
    def task_result(**values):
        values.pop("review")
        values.update(task=TaskResult(req.external_evidence_run_id, req.artifact_id, req.role, content))
        values.update(result_changes or {})
        return ExecutionResult(**values)
    with monkeypatch.context() as patch:
        patch.setattr(base, "ExecutionResult", task_result)
        return base.synthetic_observation(patch, req, runtime_selection=(retained_selection or selection).to_dict(),
            sdk_config=reported, alter_process=(lambda p:replace(p, **process)) if process else None)


def payload(req, observation, selected):
    return terminal_payload(req, observation, output_context=ProviderOutputContext(()), admitted_sdk_execution=selected)


def options():
    return dict(artifact="reviews/qa.md", started_at="2026-10-23T10:01:00Z",
        updated_at="2026-10-23T10:01:00Z", ledger_max_events=100, ledger_max_bytes=1048576,
        output_context=ProviderOutputContext(()))


def launch(item, req, selected, execution_role="consultant"):
    args = sdk_launch_args(selected)
    for flag,value in {"--role":execution_role,"--execution-role":execution_role,
        "--assigned-role":req.role,"--provider":"claude","--model":req.model}.items():
        args[args.index(flag)+1] = value
    result = run_ledger(item, *args)
    assert result.returncode == 0, result.stdout + result.stderr


def test_exact_task_settles_real_ledger_replay_without_acceptance(monkeypatch, tmp_path):
    item, req, selection, selected = fixture(tmp_path)
    launch(item, req, selected)
    obs = observed(monkeypatch, req, selection)
    result = payload(req, obs, selected)
    assert result["status"] == "completed" and result["gate"] == "none"
    assert result["assignedRole"] == result["executionRole"] == "consultant"
    assert result["authorizing"] is False and result["closesRunIds"] == []
    body = json.loads(result["resultText"])
    assert body["task"] == obs.result.task.to_dict() and "review" not in body
    (item / "reviews/qa.md").write_bytes((result["resultText"] + "\n").encode())
    terminal = receive_terminal(item, req, obs, **options())
    before = (item / "agent-runs.jsonl").read_bytes()
    assert receive_terminal(item, req, obs, **options()) == terminal
    assert (item / "agent-runs.jsonl").read_bytes() == before
    assert terminal["gate"] == "none" and terminal["authorizing"] is False
    check = run_validator(item)
    assert check.returncode == 0, check.stdout + check.stderr


@pytest.mark.parametrize("change", [{"cancelled":True},{"timed_out":True},{"target_exit_code":1}])
def test_settled_cancel_or_failure_is_blocked(monkeypatch, tmp_path, change):
    _, req, selection, selected = fixture(tmp_path)
    result = payload(req, observed(monkeypatch, req, selection, process=change), selected)
    assert result["status"] == "blocked" and result["gate"] == "none"
    assert result["closesRunIds"] == []


@pytest.mark.parametrize("change", [{"status":"incomplete", "execution_error":"fixture_failure"}, {"task":None, "status":"incomplete"}])
def test_incomplete_adapter_does_not_complete(monkeypatch, tmp_path, change):
    _, req, selection, selected = fixture(tmp_path)
    result = payload(req, observed(monkeypatch, req, selection, result_changes=change), selected)
    assert result["status"] == "blocked" and result["gate"] == "none"


@pytest.mark.parametrize("change", [{"sandboxMode":"workspace-write"},{"adapter":"openai-codex"},
    {"accountBinding":"other"},{"model":"other"}])
def test_reported_control_mismatch_not_success(monkeypatch, tmp_path, change):
    _, req, selection, selected = fixture(tmp_path)
    result = payload(req, observed(monkeypatch, req, selection, config=change), selected)
    assert result["status"] == "blocked" and result["gate"] == "none"


@pytest.mark.parametrize("kind", ["absent", "observed-only", "wrong-hash", "missing-selection"])
def test_selected_commitment_and_retained_selection_required(monkeypatch, tmp_path, kind):
    _, req, selection, selected = fixture(tmp_path)
    obs = observed(monkeypatch, req, selection)
    if kind == "absent": selected = None
    elif kind == "observed-only": selected = obs.result.sdk_execution
    elif kind == "wrong-hash": selected = {**selected,"requestSha256":"0"*64}
    else:
        obs = observed(monkeypatch, req, selection)
        object.__setattr__(obs, "runtime_selection_json", None)
    with pytest.raises(ValueError):
        payload(req, obs, selected)


@pytest.mark.parametrize("change", [{"resources_closed":False},{"cleanup_uncertain":True},{"policy_id":"foreign"}])
def test_unsettled_receipt_refused(monkeypatch, tmp_path, change):
    _, req, selection, selected = fixture(tmp_path)
    with pytest.raises(ValueError):
        payload(req, observed(monkeypatch, req, selection, process=change), selected)


def test_secret_scan_and_artifact_mismatch_preserve_ledger(monkeypatch, tmp_path):
    item, req, selection, selected = fixture(tmp_path)
    launch(item, req, selected)
    before = (item / "agent-runs.jsonl").read_bytes()
    secret = secrets.token_urlsafe(24)
    obs = observed(monkeypatch, req, selection, content=secret)
    with pytest.raises(ValueError, match="CREDENTIAL_ECHO"):
        terminal_payload(req, obs, admitted_sdk_execution=selected, output_context=ProviderOutputContext((secret.encode(),)))
    obs = observed(monkeypatch, req, selection)
    (item / "reviews/qa.md").write_bytes(b"not the result")
    with pytest.raises(ValueError, match="artifact"):
        receive_terminal(item, req, obs, **options())
    assert (item / "agent-runs.jsonl").read_bytes() == before
    recovered = payload(req, obs, selected)
    (item / "reviews/qa.md").write_bytes((recovered["resultText"] + "\n").encode())
    assert receive_terminal(item, req, obs, **options())["status"] == "completed"
    assert run_validator(item).returncode == 0


def test_review_request_cannot_receive_task_pair(monkeypatch, tmp_path):
    _, req, selection, selected = fixture(tmp_path)
    obs = observed(monkeypatch, req, selection)
    with pytest.raises(ValueError):
        payload(replace(req, role="qa-engineer", result_kind="review"), obs, selected)


@pytest.mark.parametrize("mode", ["claude-direct", "claude-bedrock", "claude-vertex"])
def test_api_cloud_provenance_uses_existing_supported_modes(monkeypatch, tmp_path, mode):
    _, req, selection, selected = fixture(tmp_path, mode)
    runtime.validate_admitted_request(req, selection)
    assert payload(req, observed(monkeypatch, req, selection), selected)["status"] == "completed"


@pytest.mark.parametrize("mode", ["claude-subscription", "claude-subscription-override", "unknown", "codex-auth-file"])
def test_unqualified_auth_mode_cannot_supply_metadata_or_received_commitment(monkeypatch, tmp_path, mode):
    _, req, selection, selected = fixture(tmp_path)
    bad = replace(selection, auth_mode=mode)
    with pytest.raises(ValueError):
        runtime.validate_admitted_request(req, bad)
    with pytest.raises(ValueError):
        runtime.selected_sdk_execution(req, bad)
    obs = observed(monkeypatch, req, selection, retained_selection=bad)
    bad_commitment = {**selected, "requestSha256":runtime.request_sha256(req, bad)}
    with pytest.raises(ValueError):
        payload(req, obs, bad_commitment)


def test_task_parser_rejects_review_pass_token(monkeypatch, tmp_path):
    import provider_prompt as owner
    _, req, selection, selected = fixture(tmp_path)
    result = payload(req, observed(monkeypatch, req, selection), selected)
    result["primaryOutcome"]["token"] = "COMPLETE:PASS"
    with pytest.raises(ValueError):
        owner.parse_provider_result(owner.SDK_RESULT_PREFIX + json.dumps(result) + "\n")

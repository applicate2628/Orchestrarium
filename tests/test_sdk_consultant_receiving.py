"""Synthetic Consultant evidence through the real ledger; no model or native launch."""
from dataclasses import replace
import json
import secrets
import pytest
import test_sdk_receiving as fixtures
from sdk_execution.contracts import ExecutionResult, TaskResult, json_text
from sdk_execution.receiving import terminal_payload, receive_terminal
from provider_prompt import ProviderOutputContext
from test_agent_run_ledger import prepare_valid_work_item, run_ledger, run_validator
from test_sdk_ledger import sdk_launch_args, SDK_CONFIG


def request(item):
    return replace(fixtures.fixture_request(item), role="consultant", result_kind="task")


def launch_args():
    args = sdk_launch_args()
    for flag in ("--role", "--execution-role", "--assigned-role"):
        args[args.index(flag) + 1] = "consultant"
    return args


def observation(monkeypatch, req, *, content="Evidence-backed advice, not acceptance.", alter_process=None):
    # Reuse the already qualified synthetic channel/process fixture, replacing
    # only the typed final evidence. No provider/client is constructed.
    def task_result(**values):
        values.pop("review")
        return ExecutionResult(task=TaskResult(req.external_evidence_run_id,
            req.artifact_id, req.role, content), **values)
    with monkeypatch.context() as patch:
        patch.setattr(fixtures, "ExecutionResult", task_result)
        return fixtures.synthetic_observation(patch, req, alter_process=alter_process)


def test_consultant_terminal_and_real_ledger_remain_nonauthorizing(monkeypatch, tmp_path):
    item = prepare_valid_work_item(tmp_path)
    launch = run_ledger(item, *launch_args())
    assert launch.returncode == 0, launch.stdout + launch.stderr
    req = request(item)
    observed = observation(monkeypatch, req)
    payload = terminal_payload(req, observed, output_context=ProviderOutputContext(()), admitted_sdk_execution=SDK_CONFIG)
    assert payload["status"] == "completed" and payload["gate"] == "none"
    assert payload["executionRole"] == payload["assignedRole"] == "consultant"
    assert payload["primaryOutcome"]["gate"] == "none"
    assert payload["authorizing"] is False and payload["closesRunIds"] == []
    assert json.loads(payload["resultText"])["task"] == observed.result.task.to_dict()
    assert "verdict" not in json.loads(payload["resultText"])
    artifact = item / "reviews/qa.md"
    artifact.write_bytes((payload["resultText"] + "\n").encode())
    options = dict(artifact="reviews/qa.md", started_at="2026-10-23T10:01:00Z",
        updated_at="2026-10-23T10:01:00Z", ledger_max_events=100, ledger_max_bytes=1048576,
        output_context=ProviderOutputContext(()))
    terminal = receive_terminal(item, req, observed, **options)
    assert terminal["executionRole"] == "consultant" and terminal["gate"] == "none"
    assert terminal["authorizing"] is False and terminal["closesRunIds"] == []
    before = (item / "agent-runs.jsonl").read_bytes()
    assert receive_terminal(item, req, observed, **options) == terminal
    assert (item / "agent-runs.jsonl").read_bytes() == before
    checked = run_validator(item)
    assert checked.returncode == 0, checked.stdout + checked.stderr


@pytest.mark.parametrize("change", [{"target_exit_code":1}, {"cancelled":True}, {"timed_out":True}])
def test_consultant_failed_process_is_blocked_not_verdict(monkeypatch, tmp_path, change):
    req = request(prepare_valid_work_item(tmp_path))
    observed = observation(monkeypatch, req, alter_process=lambda process:replace(process, **change))
    payload = terminal_payload(req, observed, output_context=ProviderOutputContext(()))
    assert payload["status"] == "blocked" and payload["gate"] == "none"
    assert payload["executionRole"] == "consultant" and payload["closesRunIds"] == []


def test_consultant_secret_scan_precedes_artifact_or_ledger(monkeypatch, tmp_path):
    item = prepare_valid_work_item(tmp_path)
    req = request(item)
    secret = secrets.token_urlsafe(24)
    observed = observation(monkeypatch, req, content=secret)
    before = (item / "agent-runs.jsonl").read_bytes() if (item / "agent-runs.jsonl").exists() else None
    with pytest.raises(ValueError, match="CREDENTIAL_ECHO"):
        terminal_payload(req, observed, output_context=ProviderOutputContext((secret.encode(),)))
    after = (item / "agent-runs.jsonl").read_bytes() if (item / "agent-runs.jsonl").exists() else None
    assert after == before


def test_consultant_rejects_review_launch_identity(monkeypatch, tmp_path):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    req = request(item)
    observed = observation(monkeypatch, req)
    payload = terminal_payload(req, observed, output_context=ProviderOutputContext(()))
    (item / "reviews/qa.md").write_bytes((payload["resultText"] + "\n").encode())
    before = (item / "agent-runs.jsonl").read_bytes()
    with pytest.raises(ValueError, match="admitted launch"):
        receive_terminal(item, req, observed, artifact="reviews/qa.md",
            started_at="2026-10-23T10:01:00Z", updated_at="2026-10-23T10:01:00Z",
            ledger_max_events=100, ledger_max_bytes=1048576, output_context=ProviderOutputContext(()))
    assert (item / "agent-runs.jsonl").read_bytes() == before


def test_consultant_preworker_failure_uses_exact_ledger_role(tmp_path):
    from test_sdk_runtime import fixture, claim
    from sdk_execution import runtime, receiving
    req, selection = fixture(tmp_path)
    req = replace(req, role="consultant", result_kind="task")
    selection = claim(req, selection)
    terminal = runtime._settle_before_worker_failure(req, selection, started_at="2026-10-23T10:00:00Z")
    run = runtime.RuntimeRun(req, selection, ProviderOutputContext(()), None, terminal,
                             "selected_codex_hook_trust_unavailable")
    payload = receiving.preworker_failure_payload(run)
    assert payload["assignedRole"] == payload["executionRole"] == "consultant"
    assert payload["status"] == "blocked" and payload["gate"] == "none"
    assert payload["authorizing"] is False and payload["closesRunIds"] == []

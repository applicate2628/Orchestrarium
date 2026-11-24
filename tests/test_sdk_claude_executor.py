"""Existing Host executor with simulated worker transport, real claim/receiving."""
import asyncio
from dataclasses import replace
from pathlib import Path
import time
from types import SimpleNamespace

import pytest
import test_sdk_claude_consultant_receiving as fixtures
from sdk_execution import runtime
from provider_prompt import ProviderOutputContext
from process_supervision.process_runner import ProcessRunnerV1


def setup(tmp_path, monkeypatch, *, denied=None, cancel=False, receiving_failure=False):
    item, req, selection, _ = fixtures.fixture(tmp_path)
    selection = replace(selection, expected_launch_sha256=None)
    effects, tools, accounts, worker_calls = [], [], [], []
    current = [req]
    def authorize(request, effect):
        assert request == req
        effects.append(effect)
        if effect == denied:
            raise ValueError("fixture authority revoked")
    def tool(request, name, args):
        assert request == req
        tools.append((name, args))
        if denied == "tool-owner": raise ValueError("fixture tool denied")
    def account(request, evidence):
        assert request == req
        accounts.append(evidence)
        return "wrong-account" if denied == "account-owner" else req.account_binding
    monkeypatch.setattr(runtime, "prepare_environment", lambda selection, source: ({}, ProviderOutputContext(())))
    monkeypatch.setattr(runtime, "_verify_runtime", lambda selected: None)
    import process_supervision.sdk_worker as worker
    def simulated(owner, request, **kwargs):
        worker_calls.append(request)
        authority = kwargs["authority"]
        authority(request, "start")
        authority(request, "account", {"kind":"account","evidence":{"phase":"before_connect","data":{}}})
        authority(request, "tool", {"kind":"tool","name":"Read","arguments":{"file_path":"relative-source.py"}})
        admitted = runtime.runtime_selection_from_dict("claude", kwargs["runtime_selection"])
        observation = fixtures.observed(monkeypatch, request, admitted)
        if receiving_failure:
            # Occupy only the authorized artifact to trigger real receipt rejection.
            (item / "executor-result.json").write_bytes(b"preexisting output")
        return observation
    monkeypatch.setattr(worker, "run_sdk_worker", simulated)
    process = ProcessRunnerV1()
    source = {"FIXTURE_ENV":"original"}
    executor = runtime.SdkReviewExecutor(request_id="task", authority=SimpleNamespace(
        resolve=lambda identifier: current[0], assert_current=authorize), selection=selection,
        process_owner=process, source_environment=source, artifact="executor-result.json",
        deadline_monotonic=time.monotonic()+120, cancellation_probe=lambda:cancel,
        started_at="2026-10-23T10:00:00Z", authorize_tool=tool, verify_account=account)
    return SimpleNamespace(item=item, req=req, executor=executor, process=process,
        effects=effects, tools=tools, accounts=accounts, worker_calls=worker_calls, current=current, source=source)


def test_existing_host_executor_runs_task_to_real_nonauthorizing_receipt(monkeypatch, tmp_path):
    case = setup(tmp_path, monkeypatch)
    with case.process:
        case.source["FIXTURE_ENV"] = "caller changed"
        assert case.executor._environment["FIXTURE_ENV"] == "original"
        result = asyncio.run(case.executor.execute(case.req))
        assert result.status == "completed" and result.task is not None and result.review is None
        assert case.executor.terminal["status"] == "completed"
        assert case.executor.terminal["gate"] == "none"
        assert case.executor.terminal["executionRole"] == "consultant"
        assert case.executor.terminal["authorizing"] is False
        assert case.executor.terminal["closesRunIds"] == []
        assert case.tools == [("Read", {"file_path":"relative-source.py"})]
        assert case.accounts == [{"phase":"before_connect","data":{}}]
        assert case.worker_calls == [case.req]
        assert (case.item / "executor-result.json").is_file()
        with pytest.raises(runtime.RuntimeBindingError, match="operation_already_consumed"):
            asyncio.run(case.executor.execute(case.req))
        assert case.worker_calls == [case.req]


@pytest.mark.parametrize("missing", ["_authorize_tool", "_verify_account"])
def test_missing_host_owner_fails_before_launch(monkeypatch, tmp_path, missing):
    case = setup(tmp_path, monkeypatch)
    setattr(case.executor, missing, None)
    with case.process, pytest.raises(runtime.RuntimeBindingError, match="owners_required"):
        asyncio.run(case.executor.execute(case.req))
    assert case.worker_calls == [] and not (case.item / "agent-runs.jsonl").exists()


def test_cancelled_preflight_does_not_claim_or_invoke(monkeypatch, tmp_path):
    case = setup(tmp_path, monkeypatch, cancel=True)
    with case.process, pytest.raises(runtime.RuntimeBindingError, match="cancelled_before_worker"):
        asyncio.run(case.executor.execute(case.req))
    assert case.worker_calls == [] and not (case.item / "agent-runs.jsonl").exists()


@pytest.mark.parametrize("denied", ["executor_start", "sdk_prepare", "account-owner", "tool-owner"])
def test_current_host_permissions_are_not_cached_as_success(monkeypatch, tmp_path, denied):
    case = setup(tmp_path, monkeypatch, denied=denied)
    with case.process, pytest.raises(ValueError):
        asyncio.run(case.executor.execute(case.req))
    assert case.executor.execution_result is None and case.executor.terminal is None
    if denied in {"executor_start", "sdk_prepare"}:
        assert not case.worker_calls and not (case.item / "agent-runs.jsonl").exists()
    else:
        assert len(case.worker_calls) == 1


def test_receiving_failure_retains_original_observation_without_reexecution(monkeypatch, tmp_path):
    case = setup(tmp_path, monkeypatch, receiving_failure=True)
    with case.process:
        with pytest.raises(ValueError):
            asyncio.run(case.executor.execute(case.req))
        assert case.executor.runtime_run is not None
        assert case.executor.runtime_run.observation.is_bound_to(case.req)
        assert case.executor.runtime_run.observation.result.task is not None
        assert case.executor.terminal is None and case.executor.execution_result is None
        with pytest.raises(runtime.RuntimeBindingError, match="operation_already_consumed"):
            asyncio.run(case.executor.execute(case.req))
        assert len(case.worker_calls) == 1
        assert (case.item / "executor-result.json").read_bytes() == b"preexisting output"


def test_request_changed_after_preflight_does_not_claim(monkeypatch, tmp_path):
    case = setup(tmp_path, monkeypatch)
    with case.process:
        assert case.executor.validate_request() == case.req
        case.current[0] = replace(case.req, scope=("changed scope",))
        with pytest.raises(runtime.RuntimeBindingError, match="admitted_request_changed"):
            asyncio.run(case.executor.execute(case.req))
    assert not case.worker_calls and not (case.item / "agent-runs.jsonl").exists()

"""Offline existing-owner parity; no Kimi binary, SDK or model is launched."""
import asyncio
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import provider_prompt as owner
from sdk_execution.contracts import ExecutionRequest, ExecutionResult
from sdk_execution.kimi import KimiAcpAdapter, KimiAdapterError

spec = importlib.util.spec_from_file_location("kimi_transport_fixture_reuse", ROOT / "tests/test_kimi_transport.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def prepared(tmp_path, monkeypatch, *, extra_args=(), **changes):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    launch = owner._prevalidate_policy_bound_external_launch("kimi", [
        "fixture", "--task-class", "review", "--role", "qa-engineer",
        "--terminal-receipt", str(tmp_path / "terminal.receipt"),
        *extra_args,
    ])
    provenance = launch.provenance
    request = ExecutionRequest(
        work_item_id=provenance.work_item, provider="kimi",
        external_dispatch_id=provenance.external_dispatch_id,
        external_evidence_run_id=provenance.external_evidence_run_id,
        artifact_id=provenance.artifact_identity, role=provenance.assigned_internal_role,
        model=provenance.model, effort=provenance.effort, cwd=str(tmp_path),
        account_binding="fixture-account", prompt="Review literal ${x} and Unicode: Привет.",
        coordinator_binding="fixture-coordinator", scope=("review",),
    )
    return launch, replace(request, **changes)


def offline_owner(monkeypatch, tmp_path, peer, *, settled=True):
    """Exercise real launch composition below Windows admission with a fake runner.

    POSIX admission is separately tested unchanged. Only the native process call
    is simulated here; the real dialogue, capture, safety, receipt and cleanup
    owners run. This fixture is not evidence of native platform settlement.
    """
    requests = []
    runners = []
    real_runner = owner.ProcessRunnerV1

    class FakeRunner(real_runner):
        def run(self, request, *, dialogue=None, **kwargs):
            requests.append(request)
            failure = None
            try:
                dialogue.handler(peer)
            except Exception as exc:
                failure = getattr(exc, "failure_id", "PSV1-KIMI-ACP-PROTOCOL")
            result = fixtures._kimi_process_result(
                dialogue.handler.result_bytes, b"", settled=settled,
                target_exit_code=0, failure_id=failure, dialogue_complete=failure is None,
            )
            result.cancelled = failure == "PSV1-CANCELLED"
            result.timed_out = False
            return result

    monkeypatch.setattr(owner, "_resolve_launch_provider_command", lambda *_: ([sys.executable], None))
    original_auth = owner.resolve_provider_auth_configuration
    monkeypatch.setattr(owner, "resolve_provider_auth_configuration", lambda provider: original_auth(provider, environment={}))
    monkeypatch.setattr(owner, "_kimi_user_home", lambda: tmp_path / "user")

    def admitted_launch(provider, argv, *, operation):
        assert provider == "kimi" and argv == []
        operation.consumed = True
        operation.require_current("kimi_launch_admission")
        selected = owner.kimi_selected_receipt(operation.prevalidated.control.kimi_capabilities)
        with owner.TerminalReceiptV1.reserve(operation.prevalidated.control.terminal_receipt) as receipt:
            with owner.ReservedExternalRunV1(receipt, operation=operation) as reserved:
                with FakeRunner() as runner:
                    runners.append(runner)
                    return owner._launch_with_runner(
                        "kimi", [], runner, prevalidated=operation.prevalidated,
                        reserved_run=reserved, kimi_observed_budget=owner.kimi_observed_receipt_budget(selected),
                    )

    monkeypatch.setattr(owner, "launch", admitted_launch)
    return requests, runners


def adapter(launch, *, current=None, records=None):
    return KimiAcpAdapter(
        prevalidated=launch, assert_current=current or (lambda *_: None),
        record=(records if records is not None else []).append,
    )


def test_existing_dialogue_readback_is_observed_not_selected():
    peer = fixtures._FakeKimiAcpPeer()
    exchange = owner.KimiAcpOneShotV1(b"literal", "/fixture")
    exchange(peer)
    assert (exchange.observed_model, exchange.observed_effort, exchange.stop_reason) == ("kimi-code/k3", "high", "end_turn")
    assert exchange.protocol_closed and exchange.cleanup_error is None
    assert not exchange.cancel_sent


def test_readback_preserves_cleanup_error_after_success():
    peer = fixtures._FakeKimiAcpPeer(eof_method="session/close")
    exchange = owner.KimiAcpOneShotV1(b"literal", "/fixture")
    with pytest.raises(ValueError):
        exchange(peer)
    assert exchange.result_bytes == b"artifact\nGATE: PASS\n"
    assert exchange.stop_reason == "end_turn"
    assert exchange.cleanup_error == "E_KIMI_ACP_CLEANUP" and not exchange.protocol_closed
    assert peer.requests[-1]["method"] == "session/delete"


def test_common_adapter_runs_existing_owner_and_preserves_native_result(tmp_path, monkeypatch, capsys):
    launch, request = prepared(tmp_path, monkeypatch)
    peer = fixtures._FakeKimiAcpPeer()
    requests, runners = offline_owner(monkeypatch, tmp_path, peer)
    effects, records = [], []
    result = asyncio.run(adapter(launch, current=lambda _, effect: effects.append(effect), records=records).execute(request))
    assert result.status == "completed", result.to_dict()
    assert result.native_result_text == "artifact\nGATE: PASS\n"
    assert result.review is None and result.sdk_execution is None
    assert result.actual_execution_path == "direct-external-cli"
    assert result.native_thread_id == "fake-session-1"
    assert result.native_turn_id is None
    assert result.protocol_closed and len(records) == 1
    receipt = owner.parse_provider_result((tmp_path / "terminal.receipt").read_text())
    assert receipt["externalDispatchId"] == request.run_id
    assert receipt["observed"] == {"toolCalls": [], "permissionDecisions": []}
    assert receipt["selected"]["permission"] == "reject"
    assert requests[0].cancellation_probe is not None
    assert requests[0].stdin_bytes is None
    assert effects == ["kimi_launch_admission", "kimi_process_start", "kimi_prompt"]
    assert runners[0]._closed
    assert "ORCHESTRARIUM_PROVIDER_RESULT" not in capsys.readouterr().out
    assert ExecutionResult.from_dict(result.to_dict()) == result


@pytest.mark.parametrize("changes", [
    {"model": "other"}, {"effort": "low"}, {"external_evidence_run_id": "wrong"},
    {"artifact_id": "wrong"}, {"role": "architecture-reviewer"}, {"cwd": "/different"},
])
def test_request_drift_stops_before_owner(tmp_path, monkeypatch, changes):
    launch, request = prepared(tmp_path, monkeypatch, **changes)
    monkeypatch.setattr(owner, "launch", lambda *_args, **_kwargs: pytest.fail("owner reached"))
    with pytest.raises(KimiAdapterError, match="binding_mismatch"):
        asyncio.run(adapter(launch).execute(request))


def test_revocation_after_model_readback_stops_prompt_and_cleans(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    peer = fixtures._FakeKimiAcpPeer()
    offline_owner(monkeypatch, tmp_path, peer)
    def current(_, effect):
        if effect == "kimi_prompt":
            raise ValueError("private authority failure")
    result = asyncio.run(adapter(launch, current=current).execute(request))
    assert result.status != "completed" and result.protocol_closed
    assert "session/prompt" not in [row["method"] for row in peer.requests]
    assert [row["method"] for row in peer.requests][-2:] == ["session/close", "session/delete"]
    assert "private authority failure" not in str(result.to_dict())


def test_cleanup_failure_retains_acquired_text(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    peer = fixtures._FakeKimiAcpPeer(eof_method="session/close")
    offline_owner(monkeypatch, tmp_path, peer)
    result = asyncio.run(adapter(launch).execute(request))
    assert result.status != "completed"
    assert result.provider_status == "completed"
    assert result.cleanup_error == "E_KIMI_ACP_CLEANUP"
    assert result.native_result_text == "artifact\nGATE: PASS\n"
    assert not result.protocol_closed


def test_process_settlement_is_not_inferred_from_protocol_close(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    offline_owner(monkeypatch, tmp_path, fixtures._FakeKimiAcpPeer(), settled=False)
    result = asyncio.run(adapter(launch).execute(request))
    assert result.protocol_closed and result.status != "completed"
    assert result.cleanup_error == "kimi_process_settlement_unavailable"


def test_unsupported_platform_hold_remains_before_receipt(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("POSIX hold")
    launch, request = prepared(tmp_path, monkeypatch)
    result = asyncio.run(adapter(launch).execute(request))
    assert result.status != "completed"
    assert not (tmp_path / "terminal.receipt").exists()


def test_cancel_uses_existing_probe_and_never_fakes_ack(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    entered, proceed = threading.Event(), threading.Event()
    peer = fixtures._FakeKimiAcpPeer()
    requests, _ = offline_owner(monkeypatch, tmp_path, peer)
    def current(_, effect):
        if effect == "kimi_process_start":
            entered.set()
            assert proceed.wait(5)
    instance = adapter(launch, current=current)
    async def run():
        task = asyncio.create_task(instance.execute(request))
        assert await asyncio.to_thread(entered.wait, 5)
        unknown = await instance.cancel("unknown")
        assert not unknown.requested
        receipt = await instance.cancel(request.run_id)
        assert receipt.requested and not receipt.acknowledged
        proceed.set()
        result = await task
        assert result.status == "interrupted"
        assert requests[0].cancellation_probe()
        assert "session/cancel" in [row["method"] for row in peer.requests]
        assert "session/prompt" not in [row["method"] for row in peer.requests]
        assert (await instance.cancel(request.run_id)).error == "already_finished"
    asyncio.run(run())


def test_repeated_caller_cancellation_retains_owned_terminal(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    requests, runners = offline_owner(monkeypatch, tmp_path, fixtures._FakeKimiAcpPeer())
    simulated_owner = owner.launch
    entered, proceed = threading.Event(), threading.Event()

    def blocked_owner(*args, **kwargs):
        code = simulated_owner(*args, **kwargs)
        entered.set()
        assert proceed.wait(5)
        return code

    monkeypatch.setattr(owner, "launch", blocked_owner)
    instance = adapter(launch)

    async def run():
        task = asyncio.create_task(instance.execute(request))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(0)
            assert not task.done(), "caller cancellation discarded the owned result"
        finally:
            proceed.set()
            outcomes = await asyncio.gather(task, return_exceptions=True)
        result = outcomes[0]
        assert isinstance(result, ExecutionResult)
        assert result.status == "interrupted" and result.provider_status == "completed"
        assert result.native_result_text == "artifact\nGATE: PASS\n"
        assert result.protocol_closed and result.cleanup_error is None
        assert len(requests) == 1 and requests[0].cancellation_probe()
        assert runners[0]._closed
        assert (await instance.cancel(request.run_id)).error == "already_finished"

    asyncio.run(run())


def test_operation_is_not_replayed(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    offline_owner(monkeypatch, tmp_path, fixtures._FakeKimiAcpPeer())
    instance = adapter(launch)
    asyncio.run(instance.execute(request))
    with pytest.raises(KimiAdapterError, match="consumed"):
        asyncio.run(instance.execute(request))


def test_owner_revalidates_capabilities_before_receipt(tmp_path, monkeypatch, capsys):
    launch, request = prepared(tmp_path, monkeypatch)
    launch.control.kimi_capabilities = owner.KimiCapabilitySelectionV1(tools=("Read",))
    binding = owner.KimiOperationBindingV1(launch, b"fixture", lambda _: None, lambda: False)
    assert owner.launch("kimi", [], operation=binding) != 0
    assert "E_KIMI_CAPABILITY_BINDING_CHANGED" in capsys.readouterr().err
    assert not (tmp_path / "terminal.receipt").exists()


def test_owner_checks_current_authority_before_effect_and_sanitizes_failure(tmp_path, monkeypatch, capsys):
    launch, request = prepared(tmp_path, monkeypatch)
    def revoked(_):
        raise ValueError("private account and directory")
    binding = owner.KimiOperationBindingV1(launch, b"fixture", revoked, lambda: False)
    assert owner.launch("kimi", [], operation=binding) != 0
    error = capsys.readouterr().err
    assert "E_KIMI_CURRENT_AUTHORITY_UNAVAILABLE" in error
    assert "private account" not in error
    assert not (tmp_path / "terminal.receipt").exists()


def test_evidence_sink_failure_does_not_erase_native_result(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    offline_owner(monkeypatch, tmp_path, fixtures._FakeKimiAcpPeer())
    def reject(_):
        raise ValueError("private sink diagnostic")
    instance = KimiAcpAdapter(prevalidated=launch, assert_current=lambda *_: None, record=reject)
    result = asyncio.run(instance.execute(request))
    assert result.status != "completed" and result.provider_status == "completed"
    assert result.native_result_text == "artifact\nGATE: PASS\n"
    assert result.capture_error == "evidence_sink_failed"
    assert len(result.observations) == 1


def test_model_drift_uses_existing_protocol_failure_and_cleanup(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    peer = fixtures._FakeKimiAcpPeer(model_config_result={"configOptions": []})
    offline_owner(monkeypatch, tmp_path, peer)
    result = asyncio.run(adapter(launch).execute(request))
    assert result.status != "completed" and result.native_result_text is None
    assert result.protocol_closed
    assert "session/prompt" not in [row["method"] for row in peer.requests]


def test_unsafe_session_id_is_not_exported(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    peer = fixtures._FakeKimiAcpPeer()
    original_read = peer.read_line
    def unsafe_read(**kwargs):
        line = original_read(**kwargs)
        return line.replace(b"fake-session-1", b"Q:/private/session")
    peer.read_line = unsafe_read
    offline_owner(monkeypatch, tmp_path, peer)
    result = asyncio.run(adapter(launch).execute(request))
    assert result.status == "completed", result.to_dict()
    assert result.native_thread_id is None
    assert "Q:/private/session" not in json.dumps(result.to_dict())


def test_existing_ledger_owner_receives_exactly_once(tmp_path, monkeypatch):
    from test_agent_run_ledger import prepare_valid_work_item
    item = prepare_valid_work_item(tmp_path)
    launch, request = prepared(tmp_path, monkeypatch, extra_args=(
        "--ledger", str(item), "--ledger-artifact", "reviews/qa.md",
        "--ledger-max-events", "100", "--ledger-max-bytes", "1048576",
    ))
    offline_owner(monkeypatch, tmp_path, fixtures._FakeKimiAcpPeer())
    writes = []
    def actual_local_writer(_runner, args):
        writes.append(list(args))
        return owner._ledger_owner().main(args) == 0
    monkeypatch.setattr(owner, "run_ledger", actual_local_writer)
    instance = adapter(launch)
    result = asyncio.run(instance.execute(request))
    assert result.status == "completed", result.to_dict()
    rows = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text().splitlines()]
    assert len(rows) == len(writes) == 2
    assert [row["eventKind"] for row in rows] == ["launch", "terminal"]
    assert rows[1]["runId"] == request.external_evidence_run_id
    assert rows[1]["launchRunId"] == request.run_id
    assert rows[1]["actualExecutionPath"] == "direct-external-cli"
    assert rows[1]["authorizing"] is False
    assert "sdkExecution" not in rows[1]
    assert result.native_result_text == "artifact\nGATE: PASS\n"
    before = (item / "agent-runs.jsonl").read_bytes()
    with pytest.raises(KimiAdapterError, match="consumed"):
        asyncio.run(instance.execute(request))
    assert (item / "agent-runs.jsonl").read_bytes() == before


def test_permission_decisions_remain_exact_and_scanned(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    peer = fixtures._FakeKimiAcpPeer(permission_request=fixtures._permission_request([
        {"optionId": "deny-exact", "name": "Reject", "kind": "reject_once"},
        {"optionId": "allow", "name": "Allow", "kind": "allow_once"},
    ]))
    offline_owner(monkeypatch, tmp_path, peer)
    result = asyncio.run(adapter(launch).execute(request))
    assert result.status == "completed", result.to_dict()
    observed = json.loads(result.observations[0].payload_json)["observed"]
    assert observed["permissionDecisions"] == [
        {"id": "1:tool-call-1", "title": "Read", "decision": "reject"},
    ]
    assert peer.client_responses[0]["result"]["outcome"]["optionId"] == "deny-exact"
    assert "private tool content" not in json.dumps(result.to_dict())


def test_missing_permission_choice_fails_without_prompt_success(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    peer = fixtures._FakeKimiAcpPeer(permission_request=fixtures._permission_request([
        {"optionId": "allow", "name": "Allow", "kind": "allow_once"},
    ]))
    offline_owner(monkeypatch, tmp_path, peer)
    result = asyncio.run(adapter(launch).execute(request))
    assert result.status != "completed" and result.provider_status is None
    assert peer.client_responses == []


def test_refusal_is_not_promoted_by_gate_looking_text(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    peer = fixtures._FakeKimiAcpPeer()
    original_read = peer.read_line
    peer.read_line = lambda **kwargs: original_read(**kwargs).replace(b'"end_turn"', b'"refusal"')
    offline_owner(monkeypatch, tmp_path, peer)
    result = asyncio.run(adapter(launch).execute(request))
    assert result.status == "failed" and result.provider_status == "failed"
    assert result.execution_error == "kimi_provider_refused"
    assert result.native_result_text == "artifact\nGATE: PASS\n"


def test_bounded_optional_observations_preserve_real_omission(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    peer = fixtures._FakeKimiAcpPeer(tool_updates=({
        "sessionUpdate": "tool_call", "toolCallId": "call-1",
        "title": "safe" * 300, "status": "completed",
    },))
    offline_owner(monkeypatch, tmp_path, peer)
    monkeypatch.setattr(owner, "kimi_observed_receipt_budget", lambda _: 100)
    result = asyncio.run(adapter(launch).execute(request))
    assert result.status == "completed", result.to_dict()
    observed = json.loads(result.observations[0].payload_json)["observed"]
    assert observed == {"toolCalls": [], "permissionDecisions": [], "observationsOmitted": True}


def test_common_observation_budget_fails_without_losing_result(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch, max_output_bytes=100)
    launch.control.result_max_bytes = 100
    offline_owner(monkeypatch, tmp_path, fixtures._FakeKimiAcpPeer())
    result = asyncio.run(adapter(launch).execute(request))
    assert result.status != "completed" and result.capture_error == "observation_limit_exceeded"
    assert result.native_result_text == "artifact\nGATE: PASS\n"
    assert result.observations == ()


def test_outer_owner_failure_preserves_acquired_outcome_without_replay(tmp_path, monkeypatch):
    launch, request = prepared(tmp_path, monkeypatch)
    offline_owner(monkeypatch, tmp_path, fixtures._FakeKimiAcpPeer())
    simulated_owner = owner.launch
    def fail_after_receiving(*args, **kwargs):
        simulated_owner(*args, **kwargs)
        raise RuntimeError("private cleanup diagnostic")
    monkeypatch.setattr(owner, "launch", fail_after_receiving)
    records = []
    result = asyncio.run(adapter(launch, records=records).execute(request))
    assert result.status == "incomplete" and result.provider_status == "completed"
    assert result.native_result_text == "artifact\nGATE: PASS\n"
    assert result.cleanup_error == "kimi_settlement_unavailable"
    assert len(records) == 1
    assert "private cleanup diagnostic" not in json.dumps(result.to_dict())

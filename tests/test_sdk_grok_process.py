"""Grok dialogue admission through existing owner; no executable is started."""
from dataclasses import replace
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from process_supervision import process_runner as owner


def process_request(runner, tmp_path):
    executable = Path(sys.executable).resolve()
    return owner.ProcessRequestV1(
        1, (str(executable), "--no-auto-update", "agent", "--no-leader", "--model", "grok-fixture", "stdio"),
        executable, str(tmp_path), (), None, time.monotonic() + 10,
        owner.CapturePolicyV1("fixture", 65536, 0, 0, 4096), runner.mint_memory_capture_sink(),
        owner.SettlePolicyV1(1), windows_argv_profile_id="native-parser-contract-v1",
        expected_executable_binding=owner.ExecutableBindingV1(str(executable), executable.stat().st_size, "0" * 64),
    )


def test_grok_dialogue_requires_existing_parser_attestation_before_any_spawn(tmp_path):
    runner = owner.ProcessRunnerV1()
    try:
        result = runner.run(process_request(runner, tmp_path), dialogue=owner.ProcessDialogueV1("grok-acp-one-shot-v1", lambda channel: None))
        assert result.failure_id == "PSV1-ARGV-CODEC-UNSUPPORTED"
        assert result.target_exit_code is None
    finally:
        runner.close()


def parser_contract():
    # Synthetic trusted-composition premise for validation only, not Grok proof.
    return owner.accept_windows_parser_contract(family="msvcrt-v1", domain="wide-utf16-v1", codec="msvcrt-v1",
        basis="offline fixture parser premise; no binary qualification", origin="accepted-operator")


@pytest.mark.parametrize("change,expected", [
    ({"argv": ("wrong",)}, "PSV1-ARGV-ATTESTATION"),
    ({"windows_argv_profile_id": "kimi-acp-one-shot-v1"}, "PSV1-REQUEST-INVALID"),
    ({"expected_executable_binding": None}, "PSV1-ARGV-ATTESTATION"),
])
def test_grok_wrong_binding_is_denied_without_a_process(tmp_path, change, expected):
    with owner.ProcessRunnerV1() as runner:
        selected = replace(process_request(runner, tmp_path), windows_parser_contract=parser_contract(), **change)
        result = runner.run(selected, dialogue=owner.ProcessDialogueV1("grok-acp-one-shot-v1", lambda channel: None))
        assert result.failure_id == expected
        assert result.target_exit_code is None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX admission hold")
def test_grok_parser_contract_cannot_bypass_existing_posix_hold(tmp_path):
    with owner.ProcessRunnerV1() as runner:
        selected = replace(process_request(runner, tmp_path), windows_parser_contract=parser_contract())
        result = runner.run(selected, dialogue=owner.ProcessDialogueV1("grok-acp-one-shot-v1", lambda channel: None))
        assert result.failure_id == "PSV1-POSIX-ORACLE-UNAVAILABLE"
        assert result.target_exit_code is None


def test_default_adapter_authority_denies_before_process_owner(tmp_path, monkeypatch):
    import asyncio
    from sdk_execution.grok import GrokAcpAdapter, GrokAcpError
    from test_sdk_grok import request
    with owner.ProcessRunnerV1() as runner:
        selected = replace(process_request(runner, tmp_path), request_id="dispatch", windows_parser_contract=parser_contract())
        monkeypatch.setattr(runner, "run", lambda *a, **k: pytest.fail("unauthorized process creation"))
        adapter = GrokAcpAdapter(owner=runner, process_request=selected, auth_method="fixture-auth")
        with pytest.raises(GrokAcpError, match="grok_execution_unavailable"):
            asyncio.run(adapter.execute(request(cwd=str(tmp_path), model="fixture")))


@pytest.fixture
def dormant_composition(monkeypatch):
    # Exercise dormant code below an unresolved admission boundary. This patch
    # is fixture-only: no selectable production flag or live policy proof exists.
    from sdk_execution import grok
    monkeypatch.setattr(grok, "_require_live_grok_policy", lambda request: None)


def settled_process(selected, *, settled):
    import hashlib
    empty = hashlib.sha256(b"").hexdigest()
    stream = owner.StreamObservationV1(0, 0, False, b"", b"", empty, empty)
    return owner.ProcessResultV1(1, owner.SETTLED_EVENT_ID, "success", "completed", None,
        str(selected.resolved_executable), "0" * 64, "0" * 64, len(selected.argv), 0, False, False, 0.1,
        owner.StdinObservationV1(1, 1, True), stream, stream,
        owner.TreeObservationV1("windows-job", True, "EMPTY" if settled else "UNKNOWN", settled, settled, settled, settled),
        settled, False, () if settled else ("fixture-unsettled",), cleanup_uncertain=not settled)


@pytest.mark.parametrize("settled", [True, False])
def test_adapter_uses_actual_owner_return_and_never_invents_account_or_receiving(tmp_path, monkeypatch, settled, dormant_composition):
    import asyncio
    import provider_prompt
    from sdk_execution.grok import GrokAcpAdapter
    from test_sdk_grok import request, Peer, successful_frames
    calls = []
    effects = []
    with owner.ProcessRunnerV1() as runner:
        selected = replace(process_request(runner, tmp_path), request_id="dispatch", windows_parser_contract=parser_contract())
        def run(actual, *, dialogue):
            calls.append(actual)
            assert dialogue.protocol_id == "grok-acp-one-shot-v1"
            dialogue.handler(Peer(successful_frames()))
            return settled_process(actual, settled=settled)
        monkeypatch.setattr(runner, "run", run)
        adapter = GrokAcpAdapter(owner=runner, process_request=selected, auth_method="fixture-auth",
            assert_current=lambda request, effect: effects.append(effect),
            output_context=provider_prompt.ProviderOutputContext(()))
        result = asyncio.run(adapter.execute(request(cwd=str(tmp_path))))
        assert len(calls) == 1
        assert calls[0].environment == selected.environment
        assert calls[0].deadline_monotonic == selected.deadline_monotonic
        assert result.native_result_text == "Native review"
        assert result.status == "incomplete"
        assert result.cleanup_error == (None if settled else "grok_process_settlement_unavailable")
        assert result.execution_error == "grok_account_readback_unavailable"
        assert "authenticate" in effects and "session/prompt" in effects
        assert adapter.process_result.tree.tree_empty is settled


def test_authority_revocation_before_prompt_never_sends_task(tmp_path, monkeypatch, dormant_composition):
    import asyncio
    import provider_prompt
    from sdk_execution.grok import GrokAcpAdapter
    from test_sdk_grok import request, Peer, successful_frames
    peer = Peer(successful_frames())
    def authority(request, effect):
        if effect == "session/prompt":
            raise ValueError("fixture private authority diagnostic")
    with owner.ProcessRunnerV1() as runner:
        selected = replace(process_request(runner, tmp_path), request_id="dispatch", windows_parser_contract=parser_contract())
        def run(actual, *, dialogue):
            dialogue.handler(peer)
            return settled_process(actual, settled=True)
        monkeypatch.setattr(runner, "run", run)
        adapter = GrokAcpAdapter(owner=runner, process_request=selected, auth_method="fixture-auth", assert_current=authority,
            output_context=provider_prompt.ProviderOutputContext(()))
        result = asyncio.run(adapter.execute(request(cwd=str(tmp_path))))
        assert not any(item.get("method") == "session/prompt" for item in peer.sent)
        assert result.execution_error == "grok_authority_denied"
        assert "private" not in str(result.to_dict())


def test_owner_failure_preserves_acquired_result_and_marks_cleanup_unavailable(tmp_path, monkeypatch, dormant_composition):
    import asyncio
    import provider_prompt
    from sdk_execution.grok import GrokAcpAdapter
    from test_sdk_grok import request, Peer, successful_frames
    with owner.ProcessRunnerV1() as runner:
        selected = replace(process_request(runner, tmp_path), request_id="dispatch", windows_parser_contract=parser_contract())
        def run(actual, *, dialogue):
            dialogue.handler(Peer(successful_frames()))
            raise OSError("fixture private owner diagnostic")
        monkeypatch.setattr(runner, "run", run)
        adapter = GrokAcpAdapter(owner=runner, process_request=selected, auth_method="fixture-auth", assert_current=lambda *args: None,
            output_context=provider_prompt.ProviderOutputContext(()))
        result = asyncio.run(adapter.execute(request(cwd=str(tmp_path))))
        assert result.native_result_text == "Native review"
        assert result.provider_status == "completed"
        assert result.execution_error == "grok_process_owner_failed"
        assert result.cleanup_error == "grok_process_settlement_unavailable"
        assert result.status == "incomplete"


def test_export_scan_failure_retains_exact_owner_result(tmp_path, monkeypatch, dormant_composition):
    import asyncio
    import provider_prompt
    from sdk_execution.grok import GrokAcpAdapter
    from test_sdk_grok import request, Peer, successful_frames
    with owner.ProcessRunnerV1() as runner:
        selected = replace(process_request(runner, tmp_path), request_id="dispatch", windows_parser_contract=parser_contract())
        process = settled_process(selected, settled=True)
        def run(actual, *, dialogue):
            dialogue.handler(Peer(successful_frames()))
            return process
        monkeypatch.setattr(runner, "run", run)
        adapter = GrokAcpAdapter(owner=runner, process_request=selected, auth_method="fixture-auth", assert_current=lambda *args: None,
            output_context=provider_prompt.ProviderOutputContext((b"Native review",)))
        with pytest.raises(ValueError):
            asyncio.run(adapter.execute(request(cwd=str(tmp_path))))
        assert adapter.process_result is process
        assert adapter.execution_result.native_result_text == "Native review"


def test_unqualified_internal_tool_enforcement_holds_even_permissive_caller(tmp_path, monkeypatch):
    import asyncio
    import provider_prompt
    from sdk_execution.grok import GrokAcpAdapter, GrokAcpError
    from test_sdk_grok import request
    with owner.ProcessRunnerV1() as runner:
        selected = replace(process_request(runner, tmp_path), request_id="dispatch", windows_parser_contract=parser_contract())
        monkeypatch.setattr(runner, "run", lambda *a, **k: pytest.fail("unqualified Grok process launched"))
        adapter = GrokAcpAdapter(owner=runner, process_request=selected, auth_method="fixture-auth",
            assert_current=lambda *args: None, output_context=provider_prompt.ProviderOutputContext(()))
        with pytest.raises(GrokAcpError, match="grok_read_only_enforcement_unavailable"):
            asyncio.run(adapter.execute(request(cwd=str(tmp_path))))
        assert adapter.process_result is None

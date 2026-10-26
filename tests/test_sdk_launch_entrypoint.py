"""Offline checks of the existing wrapper's explicit SDK selection boundary."""
from pathlib import Path
import sys
import io
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import provider_prompt as owner


@pytest.fixture(autouse=True)
def private_capture_root(tmp_path, monkeypatch):
    root = tmp_path / "capture"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(owner, "_capture_output_path", lambda _: root)


def test_sdk_binding_is_wrapper_owned_path():
    control = owner.parse_control(
        ["review", "--sdk-review-binding", "binding.json", "--", "--model", "fixture"],
        provider="codex",
    )
    assert control.sdk_review_binding == Path("binding.json")
    assert control.provider_flags == ["--model", "fixture"]


@pytest.mark.parametrize("provider", [None, "claude", "kimi", "grok"])
def test_sdk_binding_cannot_select_another_provider(provider):
    with pytest.raises(ValueError, match="E_SDK_REVIEW_PROVIDER_REQUIRED"):
        owner.parse_control(["review", "--sdk-review-binding", "binding.json"], provider=provider)


def test_no_binding_preserves_legacy_selection():
    assert owner.parse_control(["review"], provider="codex").sdk_review_binding is None


def test_sdk_binding_conflicts_are_rejected():
    with pytest.raises(ValueError, match="conflicting"):
        owner.parse_control(["review", "--sdk-review-binding", "a", "--sdk-review-binding", "b"], provider="codex")


def test_scanned_terminal_delivery_is_once_and_does_not_settle_ledger(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("SDK receipt delivery must not write ledger")
    monkeypatch.setattr(owner, "record_terminal", forbidden)
    received = []
    path = tmp_path / "terminal"
    with owner.ReservedExternalRunV1(owner.TerminalReceiptV1.reserve(path)) as reserved:
        reserved.cleanup_once()
        assert owner.commit_reserved_terminal(reserved, b"scanned terminal\n", received.append)
        assert reserved.finalized
        assert not owner.commit_reserved_terminal(reserved, b"second\n", received.append)
    assert received == [b"scanned terminal\n"]
    assert path.read_bytes() == received[0]


def test_scanned_terminal_stdout_failure_does_not_rewrite_receipt(tmp_path):
    path = tmp_path / "terminal"
    def broken(payload):
        raise BrokenPipeError()
    with owner.ReservedExternalRunV1(owner.TerminalReceiptV1.reserve(path)) as reserved:
        reserved.cleanup_once()
        assert not owner.commit_reserved_terminal(reserved, b"scanned terminal\n", broken)
        assert reserved.finalized and reserved.receipt.committed
    assert path.read_bytes() == b"scanned terminal\n"


def test_scanned_terminal_requires_cleanup_before_commit(tmp_path):
    path = tmp_path / "terminal"
    with owner.ReservedExternalRunV1(owner.TerminalReceiptV1.reserve(path)) as reserved:
        with pytest.raises(ValueError, match="CLEANUP_REQUIRED"):
            owner.commit_reserved_terminal(reserved, b"scanned terminal\n", lambda _: None)
        assert not reserved.receipt.committed


@pytest.mark.parametrize("closed", [True, False])
def test_sdk_receiving_occurs_only_after_runner_close(tmp_path, monkeypatch, closed):
    events = []
    class Runner:
        def close(self):
            events.append("close")
            return SimpleNamespace(outcome="closed" if closed else "failed-unsettled", failure_id=None if closed else "failure", unsettled_run_token_sha256=() if closed else ("run",))
    class Operation:
        recovery_max_bytes = 100
        def execute(self, process_owner):
            events.append("execute")
        def recovery_bytes(self):
            return b'{"authorizing":false}\n'
        def receive(self):
            events.append("receive")
            return SimpleNamespace(terminal_bytes=b"already scanned\n", exit_code=0)
    monkeypatch.setattr(owner, "ProcessRunnerV1", Runner)
    monkeypatch.setattr(owner.sys, "stdout", SimpleNamespace(buffer=io.BytesIO()))
    path = tmp_path / "terminal"
    with owner.ReservedExternalRunV1(owner.TerminalReceiptV1.reserve(path)) as reserved:
        code = owner._launch_sdk_review(Operation(), reserved)
    assert code == (0 if closed else 1)
    assert events == (["execute", "close", "receive"] if closed else ["execute", "close"])
    assert path.read_bytes() == (b"already scanned\n" if closed else b"")


def test_sdk_uncertain_execution_never_falls_back_to_cli(tmp_path, monkeypatch):
    events = []
    class Runner:
        def close(self):
            events.append("close")
            return SimpleNamespace(outcome="closed", failure_id=None, unsettled_run_token_sha256=())
    class Operation:
        def execute(self, process_owner):
            raise RuntimeError("uncertain process outcome")
        def receive(self):
            raise AssertionError("no fabricated preworker receipt")
    monkeypatch.setattr(owner, "ProcessRunnerV1", Runner)
    monkeypatch.setattr(owner, "finalize_reserved_run_once", lambda *a, **k: pytest.fail("CLI finalizer invoked"))
    with owner.ReservedExternalRunV1(owner.TerminalReceiptV1.reserve(tmp_path / "terminal")) as reserved:
        assert owner._launch_sdk_review(Operation(), reserved) == 1
    assert events == ["close"]


def test_sdk_close_interrupt_preserves_acquired_diagnostics(tmp_path, monkeypatch):
    class Runner:
        def close(self):
            raise KeyboardInterrupt()
    class Operation:
        recovery_max_bytes = 100
        def execute(self, process_owner):
            return object()  # Bound RuntimeRun serialization belongs to operation.
        def recovery_bytes(self):
            return b'{"authorizing":false,"receiving":"not-established"}\n'
        def receive(self):
            pytest.fail("interrupted runner close cannot establish receiving")
    monkeypatch.setattr(owner, "ProcessRunnerV1", Runner)
    with owner.ReservedExternalRunV1(owner.TerminalReceiptV1.reserve(tmp_path / "terminal")) as reserved:
        assert owner._launch_sdk_review(Operation(), reserved) == 130
    files = list((tmp_path / "capture").rglob("sdk-recovery.json"))
    assert len(files) == 1
    assert files[0].read_bytes() == Operation().recovery_bytes()
    assert not reserved.lifecycle._has_unresolved_resources()


@pytest.mark.parametrize("interrupted", [False, True])
def test_sdk_incomplete_diagnostic_write_reports_retained_directory(tmp_path, monkeypatch, capsys, interrupted):
    class Runner:
        def close(self):
            if interrupted:
                raise KeyboardInterrupt()
            return SimpleNamespace(outcome="closed", failure_id=None, unsettled_run_token_sha256=())
    class Operation:
        recovery_max_bytes = 100
        def execute(self, process_owner):
            return object()
        def recovery_bytes(self):
            return b'{"authorizing":false}\n'
        def receive(self):
            pytest.fail("failed diagnostic custody cannot receive")
    commit = owner.TerminalReceiptV1.commit
    def fail_after_write(receipt, payload):
        commit(receipt, payload)
        if receipt.path.name == "sdk-recovery.json":
            raise OSError("synthetic interrupted persistence")
    monkeypatch.setattr(owner.TerminalReceiptV1, "commit", fail_after_write)
    monkeypatch.setattr(owner, "ProcessRunnerV1", Runner)
    with owner.ReservedExternalRunV1(owner.TerminalReceiptV1.reserve(tmp_path / "terminal")) as reserved:
        assert owner._launch_sdk_review(Operation(), reserved) == (130 if interrupted else 1)
    error = capsys.readouterr().err
    assert "SDK diagnostic custody incomplete:" in error
    assert str(reserved.lifecycle.run_dir) in error
    assert "sha256=" not in error
    assert list(reserved.lifecycle.run_dir.glob("sdk-recovery.json"))

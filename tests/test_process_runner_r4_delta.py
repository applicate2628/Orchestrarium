from __future__ import annotations

import importlib.util
import os
import stat
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "process_supervision" / "process_runner.py"
PROTOCOL_PATH = ROOT / "tests" / "fixtures" / "process_supervision" / "benchmark_protocol.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _runner():
    return _load(RUNNER_PATH, "process_runner_r4_delta")


def _protocol():
    return _load(PROTOCOL_PATH, "benchmark_protocol_r4_delta")


def test_windows_conversion_failure_closes_handle_once_and_stays_uncertain() -> None:
    module = _runner()
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"h" * 16, 1))
    closes = []

    def convert(_handle, _flags):
        raise OSError(5, "conversion")

    with pytest.raises(module.ProcessSupervisionError) as caught:
        module._convert_windows_handle_to_fd(
            123,
            0,
            lifecycle,
            "stdin-parent",
            converter=convert,
            handle_closer=lambda handle: closes.append(handle) or True,
        )
    observation = lifecycle.finalize_once(time.monotonic() + 1.0)
    assert caught.value.failure_id == "PSV1-DESCRIPTOR-OWNERSHIP"
    assert closes == [123]
    assert lifecycle.resource_state("stdin-parent") == "CLOSE_UNCERTAIN"
    assert observation.resources_closed is False


def test_fd_close_failure_is_not_retried_or_marked_closed() -> None:
    module = _runner()
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"f" * 16, 1))
    calls = []
    lifecycle.register_resource("fd", lambda _remaining: None)
    lifecycle.transfer_resource(
        "fd",
        lambda _remaining: calls.append("close") or (_ for _ in ()).throw(OSError(5, "close")),
        state="FD_OWNED",
    )
    first = lifecycle.finalize_once(time.monotonic() + 1.0)
    second = lifecycle.finalize_once(time.monotonic() + 1.0)
    assert calls == ["close"]
    assert lifecycle.resource_state("fd") == "CLOSE_UNCERTAIN"
    assert first.resources_closed is second.resources_closed is False


def test_posix_dup_is_registered_before_post_dup_failure() -> None:
    module = _runner()
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"d" * 16, 1))
    source_read, source_write = os.pipe()
    duplicates = []
    try:
        with pytest.raises(RuntimeError, match="after-dup"):
            module._dup_owned_fd(
                source_read,
                lifecycle,
                "stdout-read",
                after_register=lambda descriptor: (
                    duplicates.append(descriptor),
                    (_ for _ in ()).throw(RuntimeError("after-dup")),
                )[-1],
            )
        observation = lifecycle.finalize_once(time.monotonic() + 1.0)
        assert observation.resources_closed is True
        with pytest.raises(OSError):
            os.fstat(duplicates[0])
    finally:
        os.close(source_read)
        os.close(source_write)


def test_tombstone_close_failure_blocks_execution_and_is_typed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _runner()
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"m" * 16, 1))
    original = lifecycle.close_resource

    def fail_tombstone(name: str, deadline: float) -> bool:
        if name == "cli-tombstone-descriptor":
            lifecycle.mark_resource_uncertain(name)
            return False
        return original(name, deadline)

    monkeypatch.setattr(lifecycle, "close_resource", fail_tombstone)
    with pytest.raises(module.ProcessSupervisionError) as caught:
        module._consume_request_id(
            tmp_path,
            "a" * 32,
            "b" * 64,
            lifecycle,
        )
    assert caught.value.failure_id == "PSV1-RESOURCE-CLOSE"
    assert lifecycle.resource_state("cli-tombstone-descriptor") == "CLOSE_UNCERTAIN"


def test_posix_finalizer_requires_fresh_safe_census_before_signal() -> None:
    module = _runner()
    leader = module.PosixProcessIdentityV1(100, "start", 100, 100, 1, 1)
    ledger = module.PosixGroupSettlementOracleV1(leader)
    assert ledger.observe(1, (leader,), "present", leader_reaped=False).signal_safe
    signals = []
    result = module._terminate_posix_group_fresh(
        ledger,
        deadline=time.monotonic() + 1.0,
        census=lambda _deadline: (False, (), "timeout"),
        signal_group=lambda: signals.append("signal"),
    )
    assert result.state == "AMBIGUOUS"
    assert ledger.poisoned is True
    assert signals == []


@pytest.mark.parametrize("cwd", (123, ["path"], {"path": "value"}, b"bytes"))
def test_cli_decoder_rejects_non_string_cwd(cwd: object) -> None:
    module = _runner()
    with pytest.raises(module.ProcessSupervisionError) as caught:
        module._decode_cli_cwd(cwd)
    assert caught.value.failure_id == "PSV1-REQUEST-INVALID"


def test_posix_private_metadata_requires_exact_owner_and_modes() -> None:
    module = _runner()
    uid = 1000
    directory = SimpleNamespace(st_uid=uid, st_mode=stat.S_IFDIR | 0o700)
    request = SimpleNamespace(st_uid=uid, st_mode=stat.S_IFREG | 0o600)
    module._validate_posix_private_metadata(directory, request, uid)
    for bad_directory, bad_request in (
        (SimpleNamespace(st_uid=uid + 1, st_mode=stat.S_IFDIR | 0o700), request),
        (SimpleNamespace(st_uid=uid, st_mode=stat.S_IFDIR | 0o750), request),
        (directory, SimpleNamespace(st_uid=uid + 1, st_mode=stat.S_IFREG | 0o600)),
        (directory, SimpleNamespace(st_uid=uid, st_mode=stat.S_IFREG | 0o640)),
    ):
        with pytest.raises(module.ProcessSupervisionError):
            module._validate_posix_private_metadata(bad_directory, bad_request, uid)


def test_windows_capability_decoder_is_unavailable_and_attestation_type_removed() -> None:
    module = _runner()
    nonce = b"n" * 32
    directory_digest = "d" * 64
    assert not hasattr(module, "PrivateRequestDirectoryAttestationV1")
    with pytest.raises(module.ProcessSupervisionError):
        module.decode_capability_binding(
            module.CAPABILITY_MAGIC + nonce + bytes.fromhex(directory_digest),
            platform="windows",
        )


def test_benchmark_evidence_is_transitively_immutable() -> None:
    protocol = _protocol()
    pairs = []
    for index in range(1, 6):
        order = "direct-supervised" if index % 2 else "supervised-direct"
        pairs.append(
            {
                "oneBasedIndex": index,
                "expectedOrder": order,
                "observedOrder": order,
                "directSeconds": 1.0,
                "supervisedSeconds": 1.1,
                "signedDeltaSeconds": 0.1,
            }
        )
    evidence = protocol.BenchmarkEvidenceV1.build(
        "validator", "development", pairs
    )
    before = evidence.to_dict()
    pairs[0]["directSeconds"] = 999.0
    with pytest.raises(TypeError):
        evidence.pairs[0]["direct_seconds"] = 999.0
    with pytest.raises((TypeError, AttributeError)):
        evidence.descriptive["min"] = -999.0
    assert evidence.to_dict() == before

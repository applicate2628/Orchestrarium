from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import math
import os
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "process_supervision" / "process_runner.py"
PROTOCOL_PATH = ROOT / "tests" / "fixtures" / "process_supervision" / "benchmark_protocol.py"
CHILD = ROOT / "tests" / "fixtures" / "process_supervision" / "child_helper.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _runner():
    return _load(RUNNER_PATH, "process_runner_r3_delta")


def _protocol():
    return _load(PROTOCOL_PATH, "process_runner_benchmark_r3_delta")


def _request(module, owner, *, cwd=None, sink_binding=None):
    executable = Path(sys.executable).resolve()
    argv = (sys.executable, str(CHILD), "identity")
    policy = module.CapturePolicyV1(
        "r3-delta-v1", 1024 * 1024, 64 * 1024, 128 * 1024, 64 * 1024
    )
    values = {
        "schema_version": 1,
        "argv": argv,
        "resolved_executable": executable,
        "cwd": str(ROOT) if cwd is None else cwd,
        "environment": tuple(
            module.EnvironmentRowV1(name, os.environ[name])
            for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP")
            if name in os.environ
        ),
        "stdin_bytes": None,
        "deadline_monotonic": time.monotonic() + 5.0,
        "capture_policy": policy,
        "capture_sink_binding": sink_binding or owner.mint_memory_capture_sink(),
        "settle_policy": module.SettlePolicyV1(5.0),
        "windows_argv_profile_id": (
            "python-validator-json-echo-v1" if os.name == "nt" else None
        ),
    }
    return module.ProcessRequestV1(**values)


def test_request_accepts_only_runner_minted_sealed_memory_sink() -> None:
    """Hostile protocol-shaped close/write behavior must be unreachable before spawn."""
    module = _runner()
    assert "capture_sink_binding" in {
        field.name for field in dataclasses.fields(module.ProcessRequestV1)
    }
    owner = module.ProcessRunnerV1()
    request = _request(module, owner)
    result = owner.run(request)
    assert result.outcome == "success"

    class Hostile:
        def write(self, *_args):
            raise AssertionError("hostile write reached")

        def close(self):
            time.sleep(30)

    hostile = dataclasses.replace(request, capture_sink_binding=Hostile())
    denied = owner.run(hostile)
    assert denied.failure_id == "PSV1-REQUEST-INVALID"
    assert denied.argv_count == len(hostile.argv)


def test_unknown_or_mutated_sink_binding_is_denied() -> None:
    module = _runner()
    owner = module.ProcessRunnerV1()
    binding = owner.mint_memory_capture_sink()
    mutated = object.__new__(type(binding))
    object.__setattr__(mutated, "_sink_id", "future-file-sink")
    object.__setattr__(mutated, "_seal", object())
    result = owner.run(_request(module, owner, sink_binding=mutated))
    assert result.failure_id == "PSV1-REQUEST-INVALID"


@pytest.mark.skipif(os.name == "nt", reason="Windows generic CLI unavailable")
def test_cli_expected_oserror_safe_shape_reports_cleanup_uncertainty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Capability/pre-run OSError is typed and cannot leak exception/path text."""
    module = _runner()
    ready = tmp_path / "request.ready"
    ready.write_bytes(b"request-canary")

    def fail_claim(*_args, **_kwargs):
        raise OSError(5, "PRIVATE_PATH_CANARY")

    monkeypatch.setattr(module, "_claim_request_file", fail_claim)
    code = module.main(
        ["--request-file", str(ready), "--capability-handle", "1"]
    )
    safe = json.loads(capsys.readouterr().out)
    assert code == 2
    assert safe["failureId"] == "PSV1-CLI-CLAIM"
    assert safe["resourcesClosed"] is False
    assert safe["cleanupUncertain"] is True
    assert safe["privateArtifactRetained"] is True
    assert "PRIVATE_PATH_CANARY" not in json.dumps(safe)
    assert str(ready) not in json.dumps(safe)


def test_lifecycle_close_failure_is_uncertain_and_never_retried() -> None:
    module = _runner()
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"u" * 16, 1))
    calls = []

    def fail(_remaining):
        calls.append("close")
        raise OSError(5, "close failed")

    lifecycle.register_resource("native", fail)
    first = lifecycle.finalize_once(time.monotonic() + 1.0)
    second = lifecycle.finalize_once(time.monotonic() + 1.0)
    assert calls == ["close"]
    assert first.resources_closed is False
    assert second.resources_closed is False
    assert lifecycle.resource_state("native") == "CLOSE_UNCERTAIN"


def test_resource_transfer_keeps_one_slot_and_conversion_failure_is_uncertain() -> None:
    module = _runner()
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"t" * 16, 1))
    closed = []
    lifecycle.register_resource("pipe", lambda _remaining: closed.append("handle"))
    lifecycle.transfer_resource(
        "pipe", lambda _remaining: closed.append("fd"), state="FD_OWNED"
    )
    assert lifecycle.resource_count == 1
    lifecycle.mark_resource_uncertain("pipe")
    observation = lifecycle.finalize_once(time.monotonic() + 1.0)
    assert closed == []
    assert observation.resources_closed is False
    assert lifecycle.resource_state("pipe") == "CLOSE_UNCERTAIN"


def test_posix_poison_is_monotonic_after_incomplete_or_permission_failure() -> None:
    module = _runner()
    leader = module.PosixProcessIdentityV1(10, "start", 10, 10, 1, 1)
    for cause in ("incomplete", "timeout", "permission", "cap", "parse"):
        ledger = module.PosixGroupSettlementOracleV1(leader)
        ledger.poison(cause)
        decision = ledger.observe(2, (leader,), "present", leader_reaped=False)
        assert ledger.poisoned is True
        assert decision.state == "AMBIGUOUS"
        assert decision.signal_safe is False
    ledger = module.PosixGroupSettlementOracleV1(leader)
    denied = ledger.observe(1, (leader,), "eperm", leader_reaped=False)
    later = ledger.observe(2, (leader,), "present", leader_reaped=False)
    assert denied.state == later.state == "AMBIGUOUS"
    assert later.signal_safe is False


@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf, -0.001))
def test_benchmark_rejects_nonfinite_or_negative_raw_duration(value: float) -> None:
    protocol = _protocol()
    pair = {
        "oneBasedIndex": 1,
        "expectedOrder": "direct-supervised",
        "observedOrder": "direct-supervised",
        "directSeconds": value,
        "supervisedSeconds": 1.0,
        "signedDeltaSeconds": 1.0 - value,
    }
    with pytest.raises(ValueError):
        protocol.BenchmarkEvidenceV1.build("validator", "development", [pair])


def test_benchmark_recomputes_delta_order_and_development_schema() -> None:
    protocol = _protocol()
    pairs = []
    for index in range(1, 6):
        expected = "direct-supervised" if index % 2 else "supervised-direct"
        direct = float(index)
        supervised = direct - 0.25
        pairs.append(
            {
                "oneBasedIndex": index,
                "expectedOrder": expected,
                "observedOrder": expected,
                "directSeconds": direct,
                "supervisedSeconds": supervised,
                "signedDeltaSeconds": -0.25,
            }
        )
    evidence = protocol.BenchmarkEvidenceV1.build(
        "validator", "development", pairs
    ).to_dict()
    assert set(evidence["descriptive"]) == {"min", "max", "median"}
    assert "productionP95" not in evidence
    assert "productionVerdict" not in evidence
    bad = [dict(item) for item in pairs]
    bad[1]["observedOrder"] = "direct-supervised"
    with pytest.raises(ValueError):
        protocol.BenchmarkEvidenceV1.build("validator", "development", bad)
    bad = [dict(item) for item in pairs]
    bad[0]["signedDeltaSeconds"] = 0.0
    with pytest.raises(ValueError):
        protocol.BenchmarkEvidenceV1.build("validator", "development", bad)


def test_production_benchmark_refuses_39_and_accepts_exact_40() -> None:
    protocol = _protocol()

    def pairs(count):
        return [
            {
                "oneBasedIndex": index,
                "expectedOrder": "direct-supervised" if index % 2 else "supervised-direct",
                "observedOrder": "direct-supervised" if index % 2 else "supervised-direct",
                "directSeconds": 1.0,
                "supervisedSeconds": 1.1,
                "signedDeltaSeconds": 0.1,
            }
            for index in range(1, count + 1)
        ]

    with pytest.raises(ValueError, match="40"):
        protocol.BenchmarkEvidenceV1.build("validator", "production", pairs(39))
    evidence = protocol.BenchmarkEvidenceV1.build(
        "validator", "production", pairs(40)
    ).to_dict()
    assert evidence["productionP95"] == pytest.approx(0.1)
    assert evidence["productionVerdict"] is True


def test_cwd_must_be_string_and_backend_receives_validated_canonical_value() -> None:
    module = _runner()
    owner = module.ProcessRunnerV1()
    path_request = _request(module, owner, cwd=ROOT)
    denied = owner.run(path_request)
    assert denied.failure_id == "PSV1-REQUEST-INVALID"

    observed = []

    def factory(_owner, _lifecycle):
        def backend(request, lifecycle, validated_cwd):
            observed.append((request.cwd, validated_cwd))
            raise module.ProcessSupervisionError("PSV1-CANCELLED", "cancellation")

        return backend

    owner = module.ProcessRunnerV1(backend_factory=factory)
    request = _request(module, owner, cwd=str(ROOT / "."))
    owner.run(request)
    raw, validated = observed[0]
    assert isinstance(raw, str)
    assert isinstance(validated, module.ValidatedCwdV1)
    assert validated.canonical_absolute == str(ROOT.resolve())


def test_claim_directory_binding_rejects_cross_directory_copy(tmp_path: Path) -> None:
    module = _runner()
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir(mode=0o700)
    second.mkdir(mode=0o700)
    first_digest = module.claim_directory_identity_sha256(str(first))
    second_digest = module.claim_directory_identity_sha256(str(second))
    assert first_digest != second_digest
    nonce = b"n" * 32
    capability = module.capability_binding_sha256(nonce, first_digest)
    assert module.validate_claim_directory_binding(
        first_digest, first_digest, capability, nonce
    )
    assert not module.validate_claim_directory_binding(
        first_digest, second_digest, capability, nonce
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows sealed-attestation refusal")
def test_windows_cli_refuses_legacy_unattested_capability(
    tmp_path: Path,
) -> None:
    module = _runner()
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"w" * 16, 1))
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"x" * 32)
    os.close(write_fd)
    import msvcrt

    handle = msvcrt.get_osfhandle(read_fd)
    with pytest.raises(module.ProcessSupervisionError) as caught:
        module._read_capability(handle, lifecycle)
    lifecycle.finalize_once(time.monotonic() + 1.0)
    assert (
        caught.value.failure_id
        == "PSV1-CLI-PRIVATE-DIRECTORY-UNAVAILABLE"
    )

from __future__ import annotations

import importlib.util
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
    return _load(RUNNER_PATH, "process_runner_r5_delta")


def _protocol():
    return _load(PROTOCOL_PATH, "benchmark_protocol_r5_delta")


def _request(module, owner):
    executable = Path(sys.executable).resolve()
    argv = (sys.executable, str(CHILD), "identity")
    environment = tuple(
        module.EnvironmentRowV1(name, os.environ[name])
        for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP")
        if name in os.environ
    )
    return module.ProcessRequestV1(
        1,
        argv,
        executable,
        str(ROOT),
        environment,
        None,
        time.monotonic() + 5.0,
        module.CapturePolicyV1(
            "r5-v1", 1024 * 1024, 64 * 1024, 128 * 1024, 64 * 1024
        ),
        owner.mint_memory_capture_sink(),
        module.SettlePolicyV1(5.0),
        windows_argv_profile_id=(
            "python-validator-json-echo-v1" if os.name == "nt" else None
        ),
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows CLI availability")
def test_windows_cli_refuses_before_capability_or_request_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _runner()
    events = []
    monkeypatch.setattr(
        module,
        "_claim_request_file",
        lambda *_args, **_kwargs: events.append("claim"),
    )
    monkeypatch.setattr(
        module,
        "_read_capability",
        lambda *_args, **_kwargs: events.append("capability"),
    )
    code = module.main(
        [
            "--request-file",
            str(tmp_path / "must-not-open.ready"),
            "--capability-handle",
            "123",
        ]
    )
    safe = __import__("json").loads(capsys.readouterr().out)
    assert code == 2
    assert events == []
    assert safe["failureId"] == "PSV1-CLI-PRIVATE-DIRECTORY-UNAVAILABLE"
    assert safe["resourcesClosed"] is True
    assert safe["cleanupUncertain"] is False


@pytest.mark.skipif(os.name != "nt", reason="real Windows resource ownership")
def test_real_windows_backend_registers_every_raw_handle_and_transfers_parent_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner()
    lifecycles = []
    original = module.RunLifecycleV1

    class RecordingLifecycle(original):
        def __init__(self, token):
            super().__init__(token)
            lifecycles.append(self)

    monkeypatch.setattr(module, "RunLifecycleV1", RecordingLifecycle)
    owner = module.ProcessRunnerV1()
    result = owner.run(_request(module, owner))
    assert result.outcome == "success"
    lifecycle = lifecycles[-1]
    required = {
        "windows-handle:stdin_child",
        "windows-handle:stdin_parent",
        "windows-handle:stdout_child",
        "windows-handle:stdout_parent",
        "windows-handle:stderr_child",
        "windows-handle:stderr_parent",
        "windows-handle:job",
        "windows-handle:process",
        "windows-handle:thread",
    }
    assert required <= set(lifecycle.resource_names)
    assert not any(name.startswith("windows-fd:") for name in lifecycle.resource_names)
    assert all(lifecycle.resource_state(name) == "CLOSED" for name in required)


def test_posix_popen_streams_are_lifecycle_owned_before_setup_failure() -> None:
    module = _runner()
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"p" * 16, 1))

    class Stream:
        def __init__(self):
            self.close_count = 0

        def close(self):
            self.close_count += 1

    process = type("Process", (), {})()
    process.stdin = Stream()
    process.stdout = Stream()
    process.stderr = Stream()
    module._register_posix_popen_streams(process, lifecycle)
    observation = lifecycle.finalize_once(time.monotonic() + 1.0)
    assert observation.resources_closed is True
    assert process.stdin.close_count == process.stdout.close_count == process.stderr.close_count == 1
    assert {
        "posix-popen:stdin",
        "posix-popen:stdout",
        "posix-popen:stderr",
    } <= set(lifecycle.resource_names)


def test_benchmark_direct_construction_is_impossible_and_zero_pair_cannot_serialize() -> None:
    protocol = _protocol()
    with pytest.raises(TypeError):
        protocol.BenchmarkEvidenceV1(
            "forged",
            "production",
            (),
            protocol.BenchmarkDescriptiveV1(0.0, 0.0, 0.0),
            0.0,
            True,
        )
    forged = object.__new__(protocol.BenchmarkEvidenceV1)
    object.__setattr__(forged, "scenario_id", "forged")
    object.__setattr__(forged, "cohort_kind", "production")
    object.__setattr__(forged, "pairs", ())
    with pytest.raises(ValueError):
        forged.to_dict()


def test_post_census_deadline_crossing_poisons_and_never_signals() -> None:
    module = _runner()
    leader = module.PosixProcessIdentityV1(100, "start", 100, 100, 1, 1)
    ledger = module.PosixGroupSettlementOracleV1(leader)
    assert ledger.observe(1, (leader,), "present", leader_reaped=False).signal_safe
    times = iter((0.0, 2.0))
    signals = []
    result = module._terminate_posix_group_fresh(
        ledger,
        deadline=1.0,
        census=lambda _deadline: (True, (leader,), "present"),
        signal_group=lambda: signals.append("signal"),
        clock=lambda: next(times),
    )
    assert result.state == "AMBIGUOUS"
    assert ledger.poisoned is True
    assert signals == []


def test_linux_census_checks_deadline_after_iteration_before_killpg_probe() -> None:
    module = _runner()
    times = iter((0.0, 0.0, 2.0))
    probes = []
    complete, members, state = module._linux_identity_census(
        100,
        100,
        1,
        deadline=1.0,
        clock=lambda: next(times),
        entries=lambda: (),
        killpg_probe=lambda *_args: probes.append("probe"),
    )
    assert complete is False
    assert members == ()
    assert state == "timeout"
    assert probes == []

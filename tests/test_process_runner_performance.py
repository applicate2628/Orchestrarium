from __future__ import annotations

import concurrent.futures
import ctypes
import importlib.util
import json
import math
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "process_supervision" / "process_runner.py"
CHILD = ROOT / "tests" / "fixtures" / "process_supervision" / "child_helper.py"
SUPERVISOR = ROOT / "tests" / "fixtures" / "process_supervision" / "supervisor_helper.py"
PROTOCOL_PATH = ROOT / "tests" / "fixtures" / "process_supervision" / "benchmark_protocol.py"
N = 5


def _load_runner():
    spec = importlib.util.spec_from_file_location("process_runner_benchmark", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_protocol():
    spec = importlib.util.spec_from_file_location(
        "process_runner_benchmark_protocol_runtime", PROTOCOL_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _environment(runner):
    return tuple(
        runner.EnvironmentRowV1(name, os.environ[name])
        for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if name in os.environ
    )


def _request(runner, argv: tuple[str, ...], *, limit=1024 * 1024, deadline=15.0):
    executable = Path(sys.executable).resolve()
    digest = runner._json_argv_sha256(argv)
    attestation = runner.WindowsArgvAttestationV1(
        1, "msvcrt-v1", "msvcrt-compatible-v1",
        runner.resolve_executable_identity(executable),
        runner.resolve_executable_version(executable),
        ("generic",), digest, digest, "pass",
    )
    policy = runner.CapturePolicyV1(
        "validator-benchmark-v1", limit, min(limit, 64 * 1024),
        min(limit, 128 * 1024), 64 * 1024,
    )
    return runner.ProcessRequestV1(
        1, argv, executable, str(ROOT), _environment(runner), None,
        time.monotonic() + deadline, policy, runner.ProcessRunnerV1().mint_memory_capture_sink(),
        runner.SettlePolicyV1(5.0), windows_argv_codec="msvcrt-v1",
        windows_argv_attestation=attestation,
    )


def _nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _rss_bytes() -> int:
    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(Counters),
        ctypes.c_ulong,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    assert psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    )
    return int(counters.WorkingSetSize)


def _measure_rss(call):
    baseline = _rss_bytes()
    samples = [baseline]
    stop = threading.Event()

    def sample() -> None:
        while not stop.wait(0.01):
            samples.append(_rss_bytes())

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        value = call()
    finally:
        stop.set()
        thread.join(1.0)
        samples.append(_rss_bytes())
    return value, max(0, max(samples) - baseline)


def _parent_death_iteration(marker: Path) -> tuple[float, dict[str, object]]:
    runner = _load_runner()
    supervisor = subprocess.Popen(
        [sys.executable, str(SUPERVISOR), str(RUNNER_PATH), str(CHILD), str(marker), str(ROOT)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, close_fds=True,
    )
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = ctypes.c_void_p
    handle = None
    try:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not marker.exists():
            assert supervisor.poll() is None
            time.sleep(0.01)
        assert marker.exists()
        target_pid = int(marker.read_text(encoding="utf-8"))
        target_marker = runner.get_process_start_marker(target_pid)
        supervisor_marker = runner.get_process_start_marker(supervisor.pid)
        handle = k32.OpenProcess(0x00100000 | 0x0001, False, target_pid)
        assert handle
        started = time.monotonic()
        supervisor.kill()
        supervisor.wait(timeout=5.0)
        assert k32.WaitForSingleObject(handle, 5000) == 0
        elapsed = (time.monotonic() - started) * 1000
        return elapsed, {
            "supervisorPid": supervisor.pid,
            "supervisorStartMarker": supervisor_marker,
            "targetPid": target_pid,
            "targetStartMarker": target_marker,
        }
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.wait(timeout=5.0)
        if handle:
            if k32.WaitForSingleObject(handle, 0) != 0:
                k32.TerminateProcess(handle, 1)
            k32.CloseHandle(handle)


@pytest.mark.skipif(os.name != "nt", reason="target-Windows benchmark")
def test_six_scenario_process_supervision_benchmark(tmp_path: Path) -> None:
    """N=5 nearest-rank benchmark for the six accepted Windows scenarios."""
    runner = _load_runner()
    protocol = _load_protocol()
    scenarios: dict[str, dict[str, object]] = {}
    normal_overheads: list[float] = []
    max_rss = 0
    max_writes = 0

    validators = {
        "normal-codex-validator": ROOT / "src.codex" / "skills" / "lead" / "scripts" / "validate-skill-pack.py",
        "normal-claude-validator": ROOT / "src.claude" / "agents" / "scripts" / "validate-skill-pack.py",
    }
    env = {row.name: row.value for row in _environment(runner)}
    for name, validator in validators.items():
        rss_values: list[int] = []
        writes: list[int] = []

        def direct(_index: int) -> float:
            baseline_started = time.monotonic()
            baseline = subprocess.run(
                [sys.executable, str(validator)], cwd=ROOT, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=30.0,
            )
            assert baseline.returncode == 0
            return (time.monotonic() - baseline_started) * 1000

        def supervised(_index: int) -> float:
            request = _request(runner, (sys.executable, str(validator)), deadline=30.0)
            started = time.monotonic()
            result, rss = _measure_rss(lambda: runner.ProcessRunnerV1().run(request))
            duration = (time.monotonic() - started) * 1000
            assert result.outcome == "success"
            write_count = result.stdout.persisted_bytes + result.stderr.persisted_bytes
            rss_values.append(rss)
            writes.append(write_count)
            return duration

        pairs = protocol.build_pairs(N, direct=direct, supervised=supervised)
        overheads = [float(item["signedDeltaMs"]) for item in pairs]
        durations = [float(item["supervisedMs"]) for item in pairs]
        normal_overheads.extend(overheads)
        max_rss = max(max_rss, *rss_values)
        max_writes = max(max_writes, *writes)
        scenarios[name] = {
            "n": N,
            "durationMinMs": round(min(durations), 3),
            "durationMaxMs": round(max(durations), 3),
            "durationMedianMs": round(_nearest_rank(durations, 0.5), 3),
            "pairs": pairs,
            "benchmarkEvidence": protocol.summarize_pairs(pairs, production=False),
            "maxRssDeltaBytes": max(rss_values),
            "maxPersistedBytes": max(writes),
        }

    durations = []
    rss_values = []
    writes = []
    for _ in range(N):
        request = _request(runner, (sys.executable, str(CHILD), "infinite-writer"), limit=128 * 1024)
        started = time.monotonic()
        result, rss = _measure_rss(lambda: runner.ProcessRunnerV1().run(request))
        assert result.failure_id == "PSV1-CAPTURE-LIMIT"
        assert result.tree.tree_empty
        durations.append((time.monotonic() - started) * 1000)
        rss_values.append(rss)
        writes.append(result.stdout.persisted_bytes + result.stderr.persisted_bytes)
    max_rss = max(max_rss, *rss_values)
    max_writes = max(max_writes, *writes)
    scenarios["infinite-writer"] = {
        "n": N, "minMs": round(min(durations), 3),
        "maxMs": round(max(durations), 3),
        "medianMs": round(_nearest_rank(durations, 0.5), 3),
        "maxRssDeltaBytes": max(rss_values), "maxPersistedBytes": max(writes),
    }

    durations = []
    for index in range(N):
        marker = tmp_path / f"grandchild-{index}.txt"
        request = _request(
            runner,
            (sys.executable, str(CHILD), "grandchild-retains-pipe", "--marker", str(marker), "--token", "PID", "--sleep", "30"),
            deadline=12.0,
        )
        started = time.monotonic()
        result, rss = _measure_rss(lambda: runner.ProcessRunnerV1().run(request))
        assert result.failure_id == "PSV1-TREE-SETTLEMENT" and result.tree.tree_empty
        durations.append((time.monotonic() - started) * 1000)
        max_rss = max(max_rss, rss)
    scenarios["grandchild-retained-pipe"] = {
        "n": N, "minMs": round(min(durations), 3),
        "maxMs": round(max(durations), 3),
        "medianMs": round(_nearest_rank(durations, 0.5), 3),
    }

    durations = []
    for _ in range(N):
        shared = runner.ProcessRunnerV1()
        requests = (
            _request(runner, (sys.executable, str(CHILD), "infinite-writer"), limit=64 * 1024),
            _request(runner, (sys.executable, str(CHILD), "emit", "--bytes", "1024")),
        )
        started = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(shared.run, requests))
        durations.append((time.monotonic() - started) * 1000)
        assert results[0].failure_id == "PSV1-CAPTURE-LIMIT"
        assert results[1].outcome == "success"
        assert all(item.tree.tree_empty for item in results)
    scenarios["concurrent-isolation"] = {
        "n": N, "minMs": round(min(durations), 3),
        "maxMs": round(max(durations), 3),
        "medianMs": round(_nearest_rank(durations, 0.5), 3),
    }

    parent_durations = []
    identities = []
    for index in range(N):
        duration, identity = _parent_death_iteration(tmp_path / f"parent-death-{index}.txt")
        parent_durations.append(duration)
        identities.append(identity)
    scenarios["supervisor-parent-death"] = {
        "n": N, "minMs": round(min(parent_durations), 3),
        "maxMs": round(max(parent_durations), 3),
        "medianMs": round(_nearest_rank(parent_durations, 0.5), 3),
        "identities": identities,
    }

    scenarios["resourceCaps"] = {
        "runnerRssBytes": max_rss,
        "maxPersistedBytes": max_writes,
        "rssCapBytes": 64 * 1024 * 1024,
        "capturePayloadLimitBytes": 1024 * 1024,
        "percentileMethod": "nearest-rank",
    }
    print("PROCESS_SUPERVISION_BENCHMARK=" + json.dumps(scenarios, sort_keys=True))
    assert max_rss <= 64 * 1024 * 1024
    assert max_writes <= 1024 * 1024
